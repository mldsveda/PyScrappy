"""Scraper configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


@dataclass
class ScraperConfig:
    """Configuration for all scrapers.

    Attributes:
        timeout: HTTP request timeout in seconds.
        max_retries: Number of retry attempts for failed requests.
        retry_delay: Base delay before the first retry, in seconds.
        backoff_factor: Multiplier applied to the delay after each retry, so the
            wait is ``retry_delay * backoff_factor ** (attempt - 1)``. ``2.0``
            (the default) doubles each time; ``1.0`` keeps a constant delay.
        backoff_max: Upper bound (seconds) on a single retry delay, so backoff
            can't grow without limit. ``None`` (the default) means no cap.
        retry_jitter: Whether to randomize each exponential retry delay between
            zero and its computed, capped value. Enabled by default to prevent
            concurrent requests from retrying in lockstep; set to ``False`` to
            preserve the deterministic schedule.
        rate_limit: Minimum seconds between requests to the same domain.
        obey_robots: Whether to respect host robots.txt rules and Crawl-delay.
            ``False`` (the default) does not fetch robots.txt at all.
        user_agent: A single User-Agent string to use for every request. When set,
            it overrides ``user_agents`` rotation (some sites block the default
            UAs or require a specific one). ``None`` (the default) rotates through
            ``user_agents``.
        headers: Extra HTTP headers sent on every request (e.g.
            ``{"Accept-Language": "en-US"}``). Merged under the User-Agent, and a
            per-call ``headers=`` argument still takes precedence over these.
        user_agents: List of User-Agent strings to rotate through.
        proxy: A proxy URL, e.g. ``"http://user:pass@host:port"``, or a list of
            proxy URLs to rotate through (one is picked at random per request).
            Applies to both the HTTP client and the browser backend.
        scraper_api: Optional scraping-API service to route requests through in
            order to bypass anti-bot protection on blocked sites. A dict like
            ``{"provider": "scraperapi", "api_key": "..."}``. Supported providers:
            ``"scraperapi"``, ``"scrapeops"``, ``"scrapingbee"``. When set, HTTP
            requests are sent to the service with the target URL and the service
            returns unblocked HTML. Ignored by the browser backend.
        render_js: Whether to use a browser for JS rendering.
            ``"auto"`` attempts a plain HTTP fetch first, then falls back to a browser.
        headless: Run browser in headless mode (no visible window).
        verify_ssl: Whether to verify SSL certificates.
        cache_ttl: Seconds to cache successful GET responses in memory. ``0``
            (the default) disables caching. When set, repeated requests for the
            same URL within the TTL skip the network and the rate limiter.
        cache_max_size: Maximum number of live entries in the shared response
            cache. The cache is LRU-bounded, so a long-running process (e.g. an
            MCP server) that fetches many distinct URLs stays within this cap
            rather than growing until restart. Defaults to ``512``.
        cache_dir: Directory for an optional on-disk response cache. When set (and
            ``cache_ttl > 0``), successful GETs are also persisted here so cache
            hits survive across process restarts and separate runs — the in-memory
            cache still fronts it for speed. ``None`` (the default) keeps caching
            in memory only.
        cache_dir_max_size: Maximum number of live entries in the on-disk cache,
            mirroring ``cache_max_size`` for the in-memory tier. A long-running
            process (or a large crawl reusing one ``cache_dir``) stays within
            this cap rather than growing one file per distinct URL forever.
            Defaults to ``512``. Only takes effect when ``cache_dir`` is set.
        impersonate: Impersonate a real browser's TLS/JA3 fingerprint, to get
            past anti-bot filters that block plain clients (e.g. ``"chrome"``,
            ``"chrome124"``, ``"safari"``, ``"firefox"``). Works on both the sync
            and async HTTP paths (async uses ``curl_cffi``'s ``AsyncSession``).
            Requires the optional ``curl_cffi`` dependency (``pip install
            pyscrappy[stealth]``). ``None`` (the default) uses the normal httpx
            client.
        on_request: Optional callback ``(url) -> None`` invoked once before a URL
            is fetched over the network (not on a cache hit). For progress bars /
            metrics on long crawls.
        on_retry: Optional callback ``(url, attempt, delay, error) -> None``
            invoked before each backoff sleep, where ``attempt`` is the attempt
            that just failed, ``delay`` the seconds about to be slept, and
            ``error`` the exception (or a short string for a 429).
        on_cache_hit: Optional callback ``(url) -> None`` invoked when a request
            is served from the response cache instead of the network.
            All three hooks are best-effort: a callback that raises is logged at
            debug and never breaks the request.
    """

    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0
    backoff_max: float | None = None
    rate_limit: float = 1.0
    obey_robots: bool = False
    user_agent: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    user_agents: list[str] = field(default_factory=lambda: list(_DEFAULT_USER_AGENTS))
    proxy: str | list[str] | None = None
    scraper_api: dict[str, str] | None = None
    render_js: bool | Literal["auto"] = False
    headless: bool = True
    verify_ssl: bool = True
    cache_ttl: float = 0.0
    cache_max_size: int = 512
    cache_dir: str | None = None
    cache_dir_max_size: int = 512
    impersonate: str | None = None
    retry_jitter: bool = True
    # Observability hooks (best-effort; a raising callback never breaks a scrape).
    on_request: Callable[[str], None] | None = None
    on_retry: Callable[[str, int, float, Exception | str], None] | None = None
    on_cache_hit: Callable[[str], None] | None = None

    def pick_proxy(self, exclude: str | None = None) -> str | None:
        """Return a single proxy URL (rotating if a list was configured)."""
        import random

        if not self.proxy:
            return None
        if isinstance(self.proxy, str):
            return self.proxy

        choices = [proxy for proxy in self.proxy if proxy != exclude]
        if not choices:
            return random.choice(self.proxy) if self.proxy else None
        return random.choice(choices)
