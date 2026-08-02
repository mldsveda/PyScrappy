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
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from pyscrappy.core import scraper_api
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError
from pyscrappy.core.http import (
    _CACHE_LOCK,
    _SHARED_CACHE,
    backoff_delay,
)

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
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: dict[str, float] = {}

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

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET with retries, rate-limiting, and optional caching (see HttpClient.get)."""
        cache_key = self._cache_key(url, kwargs.get("params"))
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for %s", url)
            return cached

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
            from pyscrappy.core.robots import check_robots_async
            crawl_delay = await check_robots_async(self, url)

        await self._rate_limit(url, min_delay=crawl_delay)
        extra_headers = kwargs.pop("headers", None) or {}

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                headers = self._merge_headers(extra_headers)
                resp = await client.get(url, headers=headers, follow_redirects=True, **kwargs)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", self.config.retry_delay))
                    if attempt < self.config.max_retries:
                        logger.warning("Rate-limited on %s, retrying in %.1fs", url, retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    raise RateLimitError(f"Rate-limited by {url} after {attempt} attempts")

                resp.raise_for_status()
                self._cache_put(cache_key, resp)
                return resp

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code >= 500 and attempt < self.config.max_retries:
                    await asyncio.sleep(backoff_delay(self.config, attempt))
                    continue
                raise NetworkError(f"HTTP {exc.response.status_code} from {url}") from exc

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    await asyncio.sleep(backoff_delay(self.config, attempt))
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
                    await asyncio.sleep(backoff_delay(self.config, attempt))
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

    def _build_client(self) -> httpx.AsyncClient:
        transport_kwargs: dict[str, Any] = {}
        proxy = self.config.pick_proxy()
        if proxy:
            transport_kwargs["proxy"] = proxy
        return httpx.AsyncClient(
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            **transport_kwargs,
        )

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _pick_ua(self) -> str:
        if self.config.user_agent:
            return self.config.user_agent
        return random.choice(self.config.user_agents)

    def _merge_headers(self, extra: dict[str, str]) -> dict[str, str]:
        return {**self.config.headers, "User-Agent": self._pick_ua(), **extra}

    # Cache is shared with the sync client (same module-level store + lock).

    def _cache_key(self, url: str, params: Any) -> str:
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
                del _SHARED_CACHE[key]
                return None
            return resp

    def _cache_put(self, key: str, resp: httpx.Response) -> None:
        if self.config.cache_ttl > 0:
            with _CACHE_LOCK:
                _SHARED_CACHE[key] = (time.monotonic(), resp)

    def _get_current_user_agent(self) -> str:
        return self._pick_ua()

    async def _rate_limit(self, url: str, min_delay: float | None = None) -> None:
        domain = urlparse(url).netloc
        now = time.monotonic()
        last = self._last_request_time.get(domain, 0.0)
        delay_target = self.config.rate_limit
        if min_delay is not None:
            delay_target = max(delay_target, min_delay)
        wait = delay_target - (now - last)
        if wait > 0:
            logger.debug("Rate-limiting %s: sleeping %.2fs", domain, wait)
            await asyncio.sleep(wait)
        self._last_request_time[domain] = time.monotonic()
