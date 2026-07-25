"""Abstract base scraper."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup

from pyscrappy.core.browser import BrowserManager
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.http import HttpClient
from pyscrappy.core.models import ScrapeResult


class BaseScraper(ABC):
    """Base class that all PyScrappy scrapers inherit from.

    Provides shared HTTP/browser fetching, parsing, and a consistent interface.
    Subclasses must implement :meth:`scrape`.
    """

    name: str = "base"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self.logger = logging.getLogger(f"pyscrappy.{self.name}")
        self._http: HttpClient | None = None
        self._browser: BrowserManager | None = None

    def __enter__(self) -> BaseScraper:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._http:
            self._http.close()
            self._http = None
        if self._browser:
            self._browser.close()
            self._browser = None

    @abstractmethod
    def scrape(self, **kwargs: object) -> ScrapeResult:
        """Run the scraper and return results."""

    # -- shared helpers --

    @property
    def http(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(self.config)
        return self._http

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

    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse an HTML string into a BeautifulSoup tree."""
        return BeautifulSoup(html, "lxml")

    def fetch_and_parse(self, url: str, render_js: bool = False, **kwargs: object) -> BeautifulSoup:
        """Fetch + parse in one call."""
        return self.parse_html(self.fetch_html(url, render_js=render_js, **kwargs))
