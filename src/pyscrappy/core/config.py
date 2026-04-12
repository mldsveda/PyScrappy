"""Scraper configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0)"
    " Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


@dataclass
class ScraperConfig:
    """Configuration for all scrapers.

    Attributes:
        timeout: HTTP request timeout in seconds.
        max_retries: Number of retry attempts for failed requests.
        retry_delay: Base delay between retries in seconds (exponential backoff).
        rate_limit: Minimum seconds between requests to the same domain.
        user_agents: List of User-Agent strings to rotate through.
        proxy: HTTP/SOCKS proxy URL, e.g. ``"http://user:pass@host:port"``.
        render_js: Whether to use a browser for JS rendering.
            ``"auto"`` attempts a plain HTTP fetch first, then falls back to a browser.
        headless: Run browser in headless mode (no visible window).
        verify_ssl: Whether to verify SSL certificates.
    """

    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit: float = 1.0
    user_agents: list[str] = field(default_factory=lambda: list(_DEFAULT_USER_AGENTS))
    proxy: str | None = None
    render_js: bool | Literal["auto"] = False
    headless: bool = True
    verify_ssl: bool = True
