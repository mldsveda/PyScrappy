"""Async HTTP client — the asyncio counterpart to ``HttpClient``.

Mirrors the sync client's retry, rate-limiting, User-Agent/header handling, and
the shared in-memory response cache, but built on ``httpx.AsyncClient`` so async
callers (FastAPI services, async agents) get native concurrency without pushing
blocking calls onto a thread pool.

The sync ``HttpClient`` is unchanged; this is additive.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode, urlparse

import httpx

from pyscrappy.core import scraper_api
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError
from pyscrappy.core.http import (
    _SHARED_CACHE,
    _disk_cache_for,
    _fire,
    backoff_delay,
    parse_retry_after,
)

if TYPE_CHECKING:
    # When impersonate is set, the client is the curl_cffi-backed adapter, which
    # presents the same async surface (get/post/cookies/aclose) as AsyncClient.
    from pyscrappy.core._stealth import AsyncStealthClient

logger = logging.getLogger("pyscrappy.async_http")


class AsyncHttpClient:
    """Async HTTP client wrapping httpx.AsyncClient with retries and rate-limiting.

    Usage::

        async with AsyncHttpClient(config) as client:
            html = await client.get_html("https://example.com")

    Shares the process-wide response cache with the sync ``HttpClient``, so a
    value fetched by either is visible to the other within the TTL.
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self._client: httpx.AsyncClient | AsyncStealthClient | None = None
        self._last_request_time: dict[str, float] = {}
        self._rate_limit_locks: dict[str, asyncio.Lock] = {}
        self._current_proxy: str | None = None
        # Per-client cache of RobotFileParser keyed by host (per #73). Crawl-delay
        # is computed per request from the parser, so the UA-specific value stays
        # correct even when the client rotates User-Agents.
        self._robots_cache: dict[str, Any] = {}

    async def __aenter__(self) -> AsyncHttpClient:
        self._client = self._build_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- public API --

    async def get(self, url: str, skip_robots_check: bool = False, **kwargs: Any) -> httpx.Response:
        """GET with retries, rate-limiting, and optional caching (see HttpClient.get)."""
        # The logical target URL the caller asked for; hooks report this even
        # when scraper_api routing rewrites `url` to the provider endpoint below.
        target_url = url

        cache_key = self._cache_key(url, kwargs.get("params"))
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for %s", url)
            _fire(self.config.on_cache_hit, target_url)
            return cached

        if scraper_api.is_configured(self.config.scraper_api):
            caller_params = kwargs.pop("params", None)
            if caller_params:
                sep = "&" if "?" in url else "?"
                url = url + sep + urlencode(caller_params)
            endpoint, api_params = scraper_api.build_request(url, self.config.scraper_api or {})
            url = endpoint
            kwargs["params"] = api_params

        extra_headers = kwargs.pop("headers", None) or {}
        user_agent = extra_headers.get("User-Agent") or self._pick_ua()

        crawl_delay: float | None = None
        if self.config.obey_robots and not skip_robots_check:
            from pyscrappy.core.robots import check_robots_async

            crawl_delay = await check_robots_async(self, url, user_agent=user_agent)

        await self._rate_limit(url, min_delay=crawl_delay)
        _fire(self.config.on_request, target_url)  # a network fetch is about to happen

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                client = self._ensure_client()
                headers = self._merge_headers(extra_headers, user_agent=user_agent)
                resp = await client.get(url, headers=headers, follow_redirects=True, **kwargs)

                if resp.status_code == 429:
                    retry_after = parse_retry_after(
                        resp.headers.get("Retry-After"), self.config.retry_delay
                    )
                    if attempt < self.config.max_retries:
                        logger.warning("Rate-limited on %s, retrying in %.1fs", url, retry_after)
                        _fire(
                            self.config.on_retry,
                            target_url,
                            attempt,
                            retry_after,
                            "429 Too Many Requests",
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    raise RateLimitError(f"Rate-limited by {url} after {attempt} attempts")

                resp.raise_for_status()
                self._cache_put(cache_key, resp)
                return resp

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code >= 500 and attempt < self.config.max_retries:
                    delay = backoff_delay(self.config, attempt)
                    if exc.response.status_code == 503 and "Retry-After" in exc.response.headers:
                        delay = parse_retry_after(exc.response.headers.get("Retry-After"), delay)
                    _fire(self.config.on_retry, target_url, attempt, delay, exc)
                    await self.aclose()  # close the pool; retry rebuilds + re-picks proxy
                    await asyncio.sleep(delay)
                    continue
                raise NetworkError(f"HTTP {exc.response.status_code} from {url}") from exc

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = backoff_delay(self.config, attempt)
                    _fire(self.config.on_retry, target_url, attempt, delay, exc)
                    await self.aclose()  # close the pool; retry rebuilds + re-picks proxy
                    await asyncio.sleep(delay)
                    continue

        raise NetworkError(
            f"Failed to fetch {url} after {self.config.max_retries} attempts"
        ) from last_exc

    async def get_raw(self, url: str, **kwargs: Any) -> httpx.Response:
        """Like :meth:`get` but does NOT raise on non-2xx status codes."""
        client = self._ensure_client()
        await self._rate_limit(url)
        extra_headers = kwargs.pop("headers", None) or {}
        headers = self._merge_headers(extra_headers)
        return await client.get(url, headers=headers, follow_redirects=True, **kwargs)

    async def get_html(self, url: str, **kwargs: Any) -> str:
        """Fetch a URL and return the response body as text."""
        return (await self.get(url, **kwargs)).text

    async def post_json(self, url: str, **kwargs: Any) -> str:
        """POST a request (JSON body via ``json=``) and return the response text.

        Retries on 5xx like :meth:`get`, and carries the session's cookies.
        """
        client = self._ensure_client()
        await self._rate_limit(url)
        extra_headers = kwargs.pop("headers", None) or {}

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                headers = self._merge_headers(extra_headers)
                resp = await client.post(url, headers=headers, follow_redirects=True, **kwargs)
                if resp.status_code >= 500 and attempt < self.config.max_retries:
                    delay = backoff_delay(self.config, attempt)
                    if resp.status_code == 503 and "Retry-After" in resp.headers:
                        delay = parse_retry_after(resp.headers.get("Retry-After"), delay)
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as exc:
                raise NetworkError(f"HTTP {exc.response.status_code} from {url}") from exc
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    await asyncio.sleep(backoff_delay(self.config, attempt))
                    continue

        raise NetworkError(
            f"Failed to POST {url} after {self.config.max_retries} attempts"
        ) from last_exc

    def set_cookie(self, name: str, value: str, domain: str) -> None:
        """Set a cookie on the underlying session (used before a request)."""
        self._ensure_client().cookies.set(name, value, domain=domain)

    # -- internals (mirror the sync client) --

    def _build_client(self) -> httpx.AsyncClient | AsyncStealthClient:
        proxy = self.config.pick_proxy(exclude=self._current_proxy)
        self._current_proxy = proxy
        # TLS impersonation: swap httpx for a curl_cffi AsyncSession that mimics a
        # real browser's fingerprint. It presents the same async surface
        # (get/post/cookies/aclose) and raises httpx exceptions, so the retry,
        # rate-limit, cache, and robots logic around it is unchanged.
        if self.config.impersonate:
            from pyscrappy.core._stealth import build_async_stealth_client

            return build_async_stealth_client(
                self.config.impersonate,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                proxy=proxy,
            )
        transport_kwargs: dict[str, Any] = {}
        if proxy:
            transport_kwargs["proxy"] = proxy
        return httpx.AsyncClient(
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            **transport_kwargs,
        )

    def _ensure_client(self) -> httpx.AsyncClient | AsyncStealthClient:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _pick_ua(self) -> str:
        if self.config.user_agent:
            return self.config.user_agent
        return random.choice(self.config.user_agents)

    def _merge_headers(
        self, extra: dict[str, str], user_agent: str | None = None
    ) -> dict[str, str]:
        ua = user_agent or self._pick_ua()
        return {**self.config.headers, "User-Agent": ua, **extra}

    # Cache is shared with the sync client (same module-level store + lock).

    def _cache_key(self, url: str, params: Any) -> str:
        if not params:
            return url
        try:
            items = sorted((str(k), str(v)) for k, v in dict(params).items())
        except (TypeError, ValueError):
            return url
        sep = "&" if "?" in url else "?"
        return url + sep + urlencode(items)

    def _cache_get(self, key: str) -> httpx.Response | None:
        if self.config.cache_ttl <= 0:
            return None
        hit = _SHARED_CACHE.get(key, self.config.cache_ttl)
        if hit is not None:
            return hit
        if self.config.cache_dir:
            hit = _disk_cache_for(self.config.cache_dir).get(key, self.config.cache_ttl)
            if hit is not None:
                _SHARED_CACHE.put(key, hit, self.config.cache_max_size)
            return hit
        return None

    def _cache_put(self, key: str, resp: httpx.Response) -> None:
        if self.config.cache_ttl > 0:
            _SHARED_CACHE.put(key, resp, self.config.cache_max_size)
            if self.config.cache_dir:
                _disk_cache_for(self.config.cache_dir).put(key, resp)

    async def _rate_limit(self, url: str, min_delay: float | None = None) -> None:
        domain = urlparse(url).netloc
        delay_target = self.config.rate_limit
        if min_delay is not None:
            delay_target = max(delay_target, min_delay)

        # Guard read-compute-write with a per-domain lock, held across the
        # sleep itself: that alone serializes concurrent callers onto
        # staggered slots instead of all reading the same stale `last` and
        # sleeping the same (too-short) amount, so the timestamp only needs
        # writing once per call, after the sleep completes - not reserved
        # eagerly before it, which would leave a phantom reservation (and
        # delay the next real request) if this call is cancelled mid-sleep.
        if domain not in self._rate_limit_locks:
            self._rate_limit_locks[domain] = asyncio.Lock()
        lock = self._rate_limit_locks[domain]

        async with lock:
            now = time.monotonic()
            last = self._last_request_time.get(domain, 0.0)
            wait = delay_target - (now - last)
            if wait > 0:
                logger.debug("Rate-limiting %s: sleeping %.2fs", domain, wait)
                await asyncio.sleep(wait)
            self._last_request_time[domain] = time.monotonic()
