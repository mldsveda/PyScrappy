"""HTTP client with retry, rate-limiting, and User-Agent rotation."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import random
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from pyscrappy.core import scraper_api
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError

if TYPE_CHECKING:
    # With impersonate set, the client is the curl_cffi-backed adapter, which
    # presents the same surface (get/post/cookies/close) as httpx.Client.
    from pyscrappy.core._stealth import StealthClient

logger = logging.getLogger("pyscrappy.http")


def parse_retry_after(value: str | None, default: float) -> float:
    """Parse a ``Retry-After`` header value, which RFC 7231 allows as either
    delay-seconds (e.g. ``"120"``) or an HTTP-date (e.g. ``"Wed, 21 Oct 2025 07:28:00 GMT"``).

    Returns delay in seconds (>= 0.0). If value is missing or unparseable,
    returns ``default``.
    """
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return default


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


# Default cap on the number of live response-cache entries. Bounds memory for
# long-running processes (e.g. an MCP server) that fetch many distinct URLs; a
# client may override it via config.cache_max_size.
_DEFAULT_CACHE_MAX_SIZE = 512


class _ResponseCache:
    """Process-wide response cache shared across all HttpClient/AsyncHttpClient
    instances. This lets caching survive the short-lived scraper instances that
    callers (e.g. the MCP server) create per request.

    Bounded by an LRU policy: at most ``max_size`` live entries, oldest evicted
    first on insert. TTL is still per-entry (each client passes its own on read),
    and expired entries are dropped on access — but the size cap guarantees the
    cache stays bounded even for keys that are never re-requested, which a plain
    dict could not. Guarded by a lock because scrapers may run in worker threads.
    """

    def __init__(self, max_size: int = _DEFAULT_CACHE_MAX_SIZE) -> None:
        self._store: OrderedDict[str, tuple[float, httpx.Response]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str, ttl: float) -> httpx.Response | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, resp = entry
            if time.monotonic() - ts > ttl:
                del self._store[key]  # expired
                return None
            self._store.move_to_end(key)  # mark as most-recently used
            return resp

    def put(self, key: str, resp: httpx.Response, max_size: int | None = None) -> None:
        cap = self._max_size if max_size is None else max_size
        with self._lock:
            self._store[key] = (time.monotonic(), resp)
            self._store.move_to_end(key)
            while len(self._store) > cap:
                self._store.popitem(last=False)  # evict least-recently used

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


class _DiskCache:
    """Optional on-disk response cache, so hits survive process restarts and
    separate runs — the missing half of the in-memory :class:`_ResponseCache`.

    Each entry is a small JSON file under ``cache_dir``, named by the SHA-256 of
    the cache key: ``{ts, status, headers, url, body}`` with ``ts`` a wall-clock
    time (not monotonic, which wouldn't survive a restart). TTL is checked per
    read against the caller's ``ttl``; an expired file is deleted lazily. All ops
    are best-effort — a caching layer must never break a scrape, so any OS/JSON
    error just behaves as a miss.
    """

    def __init__(self, cache_dir: str) -> None:
        self._dir = Path(cache_dir)
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        return self._dir / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")

    def get(self, key: str, ttl: float) -> httpx.Response | None:
        path = self._path(key)
        try:
            with self._lock:
                if not path.exists():
                    return None
                data = json.loads(path.read_text(encoding="utf-8"))
                if time.time() - data["ts"] > ttl:
                    path.unlink(missing_ok=True)  # expired
                    return None
            # Body is stored base64 of the raw bytes, so binary / non-UTF-8
            # responses round-trip losslessly. Reconstruct guardedly — a
            # malformed entry must behave as a miss, never raise (best-effort).
            content = base64.b64decode(data["body"])
            return httpx.Response(
                status_code=data["status"],
                headers=data.get("headers", {}),
                content=content,
                request=httpx.Request("GET", data.get("url") or "http://cached"),
            )
        except Exception:  # noqa: BLE001 - a bad cache entry is a miss, not an error
            return None

    def put(self, key: str, resp: httpx.Response) -> None:
        tmp = None
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            # The URL may come from an httpx.Response (resp.request.url) or from
            # the stealth adapter's _StealthResponse (raw .url, no .request). Read
            # it defensively so caching never raises on a stealth response.
            request = getattr(resp, "request", None)
            url = str(request.url) if request is not None else str(getattr(resp, "url", ""))
            # Store the raw bytes (base64) so binary / non-UTF-8 bodies survive
            # the round-trip intact — re-encoding resp.text would corrupt them.
            payload = {
                "ts": time.time(),
                "status": resp.status_code,
                "headers": dict(resp.headers),
                "url": url,
                "body": base64.b64encode(resp.content).decode("ascii"),
            }
            path = self._path(key)
            tmp = path.with_suffix(".tmp")
            with self._lock:
                tmp.write_text(json.dumps(payload), encoding="utf-8")
                tmp.replace(path)  # atomic
        except Exception:  # noqa: BLE001 - caching is best-effort, must never fail a scrape
            # Clean up a stray temp file if the atomic replace didn't happen.
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    def clear(self) -> None:
        try:
            with self._lock:
                for f in self._dir.glob("*.json"):
                    f.unlink(missing_ok=True)
        except OSError:
            pass


# The single shared cache instance. Kept module-level (not per-client) so it is
# shared across every scraper/client in the process.
_SHARED_CACHE = _ResponseCache()

# Disk caches keyed by directory, shared process-wide so every client pointed at
# the same cache_dir reuses one instance (and its lock).
_DISK_CACHES: dict[str, _DiskCache] = {}
_DISK_CACHES_LOCK = threading.Lock()


def _disk_cache_for(cache_dir: str) -> _DiskCache:
    # Expand ~ and normalise so "~/.cache/x" and its expanded form map to one
    # instance (and one lock), and files land in the intended home dir rather
    # than a literal "~" relative directory.
    cache_dir = str(Path(cache_dir).expanduser())
    with _DISK_CACHES_LOCK:
        dc = _DISK_CACHES.get(cache_dir)
        if dc is None:
            dc = _DiskCache(cache_dir)
            _DISK_CACHES[cache_dir] = dc
        return dc


# Retained for backward compatibility: the async client imports this lock. The
# cache now owns its own lock, so this is unused internally but kept exported.
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
        self._client: httpx.Client | StealthClient | None = None
        self._last_request_time: dict[str, float] = {}
        self._current_proxy: str | None = None
        # Per-client cache of RobotFileParser keyed by host (per #73). Crawl-delay
        # is computed per request from the parser, so the UA-specific value stays
        # correct even when the client rotates User-Agents.
        self._robots_cache: dict[str, Any] = {}

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

    def get(self, url: str, skip_robots_check: bool = False, **kwargs: Any) -> httpx.Response:
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

        extra_headers = kwargs.pop("headers", None) or {}
        user_agent = extra_headers.get("User-Agent") or self._pick_ua()

        crawl_delay: float | None = None
        if self.config.obey_robots and not skip_robots_check:
            from pyscrappy.core.robots import check_robots_sync

            crawl_delay = check_robots_sync(self, url, user_agent=user_agent)

        self._rate_limit(url, min_delay=crawl_delay)

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                client = self._ensure_client()
                headers = self._merge_headers(extra_headers, user_agent=user_agent)
                resp = client.get(url, headers=headers, follow_redirects=True, **kwargs)

                if resp.status_code == 429:
                    retry_after = parse_retry_after(
                        resp.headers.get("Retry-After"), self.config.retry_delay
                    )
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
                    if exc.response.status_code == 503 and "Retry-After" in exc.response.headers:
                        delay = parse_retry_after(exc.response.headers.get("Retry-After"), delay)
                    logger.warning(
                        "Server error %s on %s, retry %d in %.1fs",
                        exc.response.status_code,
                        url,
                        attempt,
                        delay,
                    )
                    self.close()  # close the pool; retry rebuilds + re-picks proxy
                    time.sleep(delay)
                    continue
                raise NetworkError(f"HTTP {exc.response.status_code} from {url}") from exc

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning("Request error on %s, retry %d in %.1fs", url, attempt, delay)
                    self.close()  # close the pool; retry rebuilds + re-picks proxy
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
                    delay = self._backoff_delay(attempt)
                    if resp.status_code == 503 and "Retry-After" in resp.headers:
                        delay = parse_retry_after(resp.headers.get("Retry-After"), delay)
                    time.sleep(delay)
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

    def _build_client(self) -> httpx.Client | StealthClient:
        proxy = self.config.pick_proxy(exclude=self._current_proxy)
        self._current_proxy = proxy
        # TLS impersonation: swap httpx for a curl_cffi-backed client that mimics a
        # real browser's fingerprint. It presents the same interface HttpClient
        # uses (get/post/cookies/close) and raises httpx exceptions, so the retry,
        # rate-limit, cache, and robots logic around it is unchanged.
        if self.config.impersonate:
            from pyscrappy.core._stealth import build_stealth_client

            return build_stealth_client(
                self.config.impersonate,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
                proxy=proxy,
            )
        transport_kwargs: dict[str, Any] = {}
        if proxy:
            transport_kwargs["proxy"] = proxy
        return httpx.Client(
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            **transport_kwargs,
        )

    def _ensure_client(self) -> httpx.Client | StealthClient:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _pick_ua(self) -> str:
        # A configured single user_agent overrides rotation.
        if self.config.user_agent:
            return self.config.user_agent
        return random.choice(self.config.user_agents)

    def _merge_headers(
        self, extra: dict[str, str], user_agent: str | None = None
    ) -> dict[str, str]:
        """Build the request headers: config.headers (lowest priority), then the
        chosen User-Agent, then per-call headers (highest priority)."""
        ua = user_agent or self._pick_ua()
        return {**self.config.headers, "User-Agent": ua, **extra}

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
        sep = "&" if "?" in url else "?"
        return url + sep + urlencode(items)

    def _cache_get(self, key: str) -> httpx.Response | None:
        if self.config.cache_ttl <= 0:
            return None
        # Memory first (fast); fall back to disk (survives restarts) and promote
        # a disk hit back into memory so the next read is fast.
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

    @staticmethod
    def clear_cache() -> None:
        """Empty the process-wide in-memory response cache. (The on-disk cache,
        if configured, persists by design — delete its ``cache_dir`` to clear it.)"""
        _SHARED_CACHE.clear()

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
