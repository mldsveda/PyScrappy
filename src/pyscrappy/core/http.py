"""HTTP client with retry, rate-limiting, and User-Agent rotation."""

from __future__ import annotations

import logging
import random
import threading
import time
from typing import Any

import httpx

from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError

logger = logging.getLogger("pyscrappy.http")

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

        client = self._ensure_client()
        self._rate_limit(url)

        # Merge any caller-supplied headers on top of a rotated User-Agent,
        # so scrapers can add site-specific headers (e.g. Referer) without
        # colliding with the headers kwarg httpx expects.
        extra_headers = kwargs.pop("headers", None) or {}

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                headers = {"User-Agent": self._pick_ua(), **extra_headers}
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
                    delay = self.config.retry_delay * (2 ** (attempt - 1))
                    logger.warning("Server error %s on %s, retry %d in %.1fs",
                                   exc.response.status_code, url, attempt, delay)
                    time.sleep(delay)
                    continue
                raise NetworkError(
                    f"HTTP {exc.response.status_code} from {url}"
                ) from exc

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** (attempt - 1))
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
        headers = {"User-Agent": self._pick_ua(), **extra_headers}
        return client.get(url, headers=headers, follow_redirects=True, **kwargs)

    def get_html(self, url: str, **kwargs: Any) -> str:
        """Fetch a URL and return the response body as text."""
        return self.get(url, **kwargs).text

    # -- internals --

    def _build_client(self) -> httpx.Client:
        transport_kwargs: dict[str, Any] = {}
        if self.config.proxy:
            transport_kwargs["proxy"] = self.config.proxy
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
        return random.choice(self.config.user_agents)

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

    def _rate_limit(self, url: str) -> None:
        from urllib.parse import urlparse

        domain = urlparse(url).netloc
        now = time.monotonic()
        last = self._last_request_time.get(domain, 0.0)
        wait = self.config.rate_limit - (now - last)
        if wait > 0:
            logger.debug("Rate-limiting %s: sleeping %.2fs", domain, wait)
            time.sleep(wait)
        self._last_request_time[domain] = time.monotonic()
