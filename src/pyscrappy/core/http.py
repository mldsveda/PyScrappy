"""HTTP client with retry, rate-limiting, and User-Agent rotation."""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from pyscrappy.core import scraper_api
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError

logger = logging.getLogger("pyscrappy.http")


def backoff_delay(config: ScraperConfig, attempt: int) -> float:
    """Retry delay (seconds) before the given attempt (1-indexed), using the
    config's base delay, backoff factor, and optional cap:
    ``retry_delay * backoff_factor ** (attempt - 1)``, clamped to ``backoff_max``.

    Module-level so scrapers with their own retry loops (e.g. the stock scraper's
    Yahoo 429 handling) honor the same configurable backoff as HttpClient.
    """
    delay = config.retry_delay * (config.backoff_factor ** (attempt - 1))
    if config.backoff_max is not None:
        delay = min(delay, config.backoff_max)
    return delay


# Process-wide response cache, shared across all HttpClient instances. This lets
# caching survive the short-lived scraper instances that callers (e.g. the MCP
# server) create per request. Entries are (monotonic timestamp, response). Only
# populated when a client's config.cache_ttl > 0; guarded by a lock because
# scrapers may run in worker threads.
_SHARED_CACHE: dict[str, tuple[float, httpx.Response]] = {}
_CACHE_LOCK = threading.Lock()


class HttpClient:
    """Sync HTTP client wrapping httpx with automatic retries and rate-limiting.

    Usage::

        config = ScraperConfig(timeout=20, max_retries=2)
        with HttpClient(config) as client:
            html = client.get_html("https://example.com")
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self._client: httpx.Client | None = None
        self._last_request_time: dict[str, float] = {}

    # -- context manager --

    def __enter__(self) -> HttpClient:
        self._client = self._build_client()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # -- public API --

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Perform a GET request with retries and rate-limiting.

        When ``config.cache_ttl > 0``, a successful response is cached in memory
        and returned for repeat requests within the TTL, skipping both the
        network and the rate limiter.
        """
        cache_key = self._cache_key(url, kwargs.get("params"))
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for %s", url)
            return cached

        # Route through a scraping-API service if configured, so blocked sites
        # come back unblocked. Any caller params are folded into the *target*
        # URL first, then the whole URL is handed to the service endpoint.
        if scraper_api.is_configured(self.config.scraper_api):
            caller_params = kwargs.pop("params", None)
            if caller_params:
                sep = "&" if "?" in url else "?"
                url = url + sep + urlencode(caller_params)
            endpoint, api_params = scraper_api.build_request(url, self.config.scraper_api or {})
            url = endpoint
            kwargs["params"] = api_params

        client = self._ensure_client()
        crawl_delay: float | None = None
        if self.config.obey_robots:
            from pyscrappy.core.robots import check_robots_sync
            crawl_delay = check_robots_sync(self, url)

        self._rate_limit(url, min_delay=crawl_delay)

        # Merge any caller-supplied headers on top of a rotated User-Agent,
        # so scrapers can add site-specific headers (e.g. Referer) without
        # colliding with the headers kwarg httpx expects.
        extra_headers = kwargs.pop("headers", None) or {}

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                headers = self._merge_headers(extra_headers)
                resp = client.get(url, headers=headers, follow_redirects=True, **kwargs)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", self.config.retry_delay))
                    if attempt < self.config.max_retries:
                        logger.warning("Rate-limited on %s, retrying in %.1fs", url, retry_after)
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(f"Rate-limited by {url} after {attempt} attempts")

                resp.raise_for_status()
                self._cache_put(cache_key, resp)
                return resp

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code >= 500 and attempt < self.config.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Server error %s on %s, retry %d in %.1fs",
                        exc.response.status_code,
                        url,
                        attempt,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise NetworkError(f"HTTP {exc.response.status_code} from {url}") from exc

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning("Request error on %s, retry %d in %.1fs", url, attempt, delay)
                    time.sleep(delay)
                    continue

        raise NetworkError(
            f"Failed to fetch {url} after {self.config.max_retries} attempts"
        ) from last_exc

    def get_raw(self, url: str, **kwargs: Any) -> httpx.Response:
        """Like :meth:`get` but does NOT raise on non-2xx status codes.

        Useful when the caller needs to inspect the status code itself
        (e.g. to detect auth failures and retry with new credentials).
        """
        client = self._ensure_client()
        self._rate_limit(url)
        extra_headers = kwargs.pop("headers", None) or {}
        headers = self._merge_headers(extra_headers)
        return client.get(url, headers=headers, follow_redirects=True, **kwargs)

    def post_json(self, url: str, **kwargs: Any) -> str:
        """POST a request (JSON body via ``json=``) and return the response text.

        Retries on 5xx like :meth:`get`, and carries the session's cookies.
        """
        client = self._ensure_client()
        self._rate_limit(url)
        extra_headers = kwargs.pop("headers", None) or {}

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                headers = self._merge_headers(extra_headers)
                resp = client.post(url, headers=headers, follow_redirects=True, **kwargs)
                if resp.status_code >= 500 and attempt < self.config.max_retries:
                    time.sleep(self._backoff_delay(attempt))
                    continue
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as exc:
                raise NetworkError(f"HTTP {exc.response.status_code} from {url}") from exc
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    time.sleep(self._backoff_delay(attempt))
                    continue

        raise NetworkError(
            f"Failed to POST {url} after {self.config.max_retries} attempts"
        ) from last_exc

    def set_cookie(self, name: str, value: str, domain: str) -> None:
        """Set a cookie on the underlying session (used before a request)."""
        self._ensure_client().cookies.set(name, value, domain=domain)

    def get_html(self, url: str, **kwargs: Any) -> str:
        """Fetch a URL and return the response body as text."""
        return self.get(url, **kwargs).text

    # -- internals --

    def _build_client(self) -> httpx.Client:
        transport_kwargs: dict[str, Any] = {}
        proxy = self.config.pick_proxy()
        if proxy:
            transport_kwargs["proxy"] = proxy
        return httpx.Client(
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            **transport_kwargs,
        )

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _pick_ua(self) -> str:
        # A configured single user_agent overrides rotation.
        if self.config.user_agent:
            return self.config.user_agent
        return random.choice(self.config.user_agents)

    def _merge_headers(self, extra: dict[str, str]) -> dict[str, str]:
        """Build the request headers: config.headers (lowest priority), then the
        chosen User-Agent, then per-call headers (highest priority)."""
        return {**self.config.headers, "User-Agent": self._pick_ua(), **extra}

    def _backoff_delay(self, attempt: int) -> float:
        """Retry delay for this client's config (see module-level backoff_delay)."""
        return backoff_delay(self.config, attempt)

    # -- caching --

    def _cache_key(self, url: str, params: Any) -> str:
        """Build a cache key from the URL and any query params."""
        if not params:
            return url
        try:
            items = sorted((str(k), str(v)) for k, v in dict(params).items())
        except (TypeError, ValueError):
            return url
        return url + "?" + "&".join(f"{k}={v}" for k, v in items)

    def _cache_get(self, key: str) -> httpx.Response | None:
        if self.config.cache_ttl <= 0:
            return None
        with _CACHE_LOCK:
            entry = _SHARED_CACHE.get(key)
            if entry is None:
                return None
            ts, resp = entry
            if time.monotonic() - ts > self.config.cache_ttl:
                del _SHARED_CACHE[key]  # expired
                return None
            return resp

    def _cache_put(self, key: str, resp: httpx.Response) -> None:
        if self.config.cache_ttl > 0:
            with _CACHE_LOCK:
                _SHARED_CACHE[key] = (time.monotonic(), resp)

    @staticmethod
    def clear_cache() -> None:
        """Empty the process-wide response cache."""
        with _CACHE_LOCK:
            _SHARED_CACHE.clear()

    def _get_current_user_agent(self) -> str:
        return self._pick_ua()

    def _rate_limit(self, url: str, min_delay: float | None = None) -> None:
        from urllib.parse import urlparse

        domain = urlparse(url).netloc
        now = time.monotonic()
        last = self._last_request_time.get(domain, 0.0)
        delay_target = self.config.rate_limit
        if min_delay is not None:
            delay_target = max(delay_target, min_delay)
        wait = delay_target - (now - last)
        if wait > 0:
            logger.debug("Rate-limiting %s: sleeping %.2fs", domain, wait)
            time.sleep(wait)
        self._last_request_time[domain] = time.monotonic()
