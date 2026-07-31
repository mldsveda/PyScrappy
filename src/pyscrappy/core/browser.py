"""Playwright browser lifecycle manager."""

from __future__ import annotations

import logging
from typing import Any

from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import BrowserNotInstalledError

logger = logging.getLogger("pyscrappy.browser")


class BrowserManager:
    """Manages a Playwright browser instance with context-manager cleanup.

    Usage::

        config = ScraperConfig(headless=True)
        with BrowserManager(config) as bm:
            html = bm.get_html("https://example.com")
            html2 = bm.get_html("https://example.com/page2", wait_for="networkidle")
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self._pw: Any = None
        self._browser: Any = None

    def __enter__(self) -> BrowserManager:
        self._start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise BrowserNotInstalledError()

        self._pw = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": self.config.headless}
        proxy = self.config.pick_proxy()
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
        try:
            self._browser = self._pw.chromium.launch(**launch_kwargs)
        except Exception as exc:
            self._pw.stop()
            self._pw = None
            if "Executable doesn't exist" in str(exc):
                raise BrowserNotInstalledError() from exc
            raise

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._pw:
            self._pw.stop()
            self._pw = None

    def get_html(
        self,
        url: str,
        wait_for: str = "domcontentloaded",
        wait_timeout: float | None = None,
        scroll_pages: int = 0,
    ) -> str:
        """Navigate to a URL and return the rendered HTML.

        Args:
            url: The URL to navigate to.
            wait_for: Playwright wait condition — ``"domcontentloaded"``,
                ``"load"``, or ``"networkidle"``.
            wait_timeout: Override timeout in ms for the page load.
            scroll_pages: Number of times to scroll to the bottom (for infinite-scroll pages).
        """
        if not self._browser:
            self._start()

        timeout_ms = int((wait_timeout or self.config.timeout) * 1000)
        ua = self.config.user_agents[0] if self.config.user_agents else None

        context = self._browser.new_context(user_agent=ua)
        page = context.new_page()
        try:
            page.goto(url, wait_until=wait_for, timeout=timeout_ms)

            for _ in range(scroll_pages):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)

            return page.content()
        finally:
            page.close()
            context.close()

    def screenshot(self, url: str, path: str, full_page: bool = True) -> None:
        """Take a screenshot of a page."""
        if not self._browser:
            self._start()

        context = self._browser.new_context()
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=int(self.config.timeout * 1000))
            page.screenshot(path=path, full_page=full_page)
        finally:
            page.close()
            context.close()
