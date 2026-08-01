"""Abstract base scraper."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup

from pyscrappy.core.browser import BrowserManager
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.http import HttpClient
from pyscrappy.core.models import ScrapeResult

if TYPE_CHECKING:
    from pyscrappy.core.async_http import AsyncHttpClient


class BaseScraper(ABC):
    """Base class that all PyScrappy scrapers inherit from.

    Provides shared HTTP/browser fetching, parsing, and a consistent interface.
    Subclasses must implement :meth:`scrape`.

    Every scraper also exposes an async counterpart, :meth:`scrape_async`, backed
    by the shared async helpers below (:attr:`async_http`, :meth:`fetch_html_async`,
    :meth:`fetch_and_parse_async`). The async path uses a native ``AsyncHttpClient``
    and reuses the same synchronous parsing/extraction, so no scraping logic is
    duplicated. JS rendering is sync-only (the browser backend), so ``scrape_async``
    always fetches over plain HTTP; use :meth:`scrape` with ``render_js`` for pages
    that need a browser.
    """

    name: str = "base"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self.logger = logging.getLogger(f"pyscrappy.{self.name}")
        self._http: HttpClient | None = None
        self._async_http: AsyncHttpClient | None = None
        self._browser: BrowserManager | None = None

    def __enter__(self) -> BaseScraper:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    async def __aenter__(self) -> BaseScraper:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def close(self) -> None:
        if self._http:
            self._http.close()
            self._http = None
        if self._browser:
            self._browser.close()
            self._browser = None

    async def aclose(self) -> None:
        """Close async resources (the async HTTP client). Sync resources, if any
        were also opened, are closed too."""
        if self._async_http:
            await self._async_http.aclose()
            self._async_http = None
        self.close()

    @abstractmethod
    def scrape(self, **kwargs: object) -> ScrapeResult:
        """Run the scraper and return results."""

    async def scrape_async(self, **kwargs: object) -> ScrapeResult:
        """Async counterpart to :meth:`scrape`.

        Scrapers override this with a version that awaits the async fetch helpers
        and reuses the same parsing/extraction as :meth:`scrape`. The default
        implementation raises, so a scraper that hasn't been ported is explicit
        rather than silently falling back to blocking I/O.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not provide a native async scrape yet; "
            "use the synchronous scrape() instead."
        )

    # -- shared helpers --

    @property
    def http(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(self.config)
        return self._http

    @property
    def async_http(self) -> AsyncHttpClient:
        if self._async_http is None:
            from pyscrappy.core.async_http import AsyncHttpClient

            self._async_http = AsyncHttpClient(self.config)
        return self._async_http

    @property
    def browser(self) -> BrowserManager:
        if self._browser is None:
            self._browser = BrowserManager(self.config)
            self._browser._start()
        return self._browser

    def fetch_html(self, url: str, render_js: bool = False, **kwargs: object) -> str:
        """Fetch a page's HTML, optionally rendering JavaScript."""
        if render_js:
            return self.browser.get_html(url, **kwargs)  # type: ignore[arg-type]
        return self.http.get_html(url, **kwargs)

    async def fetch_html_async(self, url: str, **kwargs: object) -> str:
        """Async fetch of a page's HTML over plain HTTP (no JS rendering).

        The browser backend is sync-only, so there is no ``render_js`` option here.
        """
        return await self.async_http.get_html(url, **kwargs)

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse an HTML string into a BeautifulSoup tree."""
        return BeautifulSoup(html, "lxml")

    def fetch_and_parse(self, url: str, render_js: bool = False, **kwargs: object) -> BeautifulSoup:
        """Fetch + parse in one call."""
        return self.parse_html(self.fetch_html(url, render_js=render_js, **kwargs))

    async def fetch_and_parse_async(self, url: str, **kwargs: object) -> BeautifulSoup:
        """Async fetch + parse in one call (plain HTTP, no JS rendering)."""
        return self.parse_html(await self.fetch_html_async(url, **kwargs))
