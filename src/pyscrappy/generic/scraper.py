"""Generic all-in-one scraper — the star feature of PyScrappy."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult
from pyscrappy.generic.extractors import (
    ImageExtractor,
    LinkExtractor,
    MetadataExtractor,
    TableExtractor,
    TextExtractor,
)
from pyscrappy.generic.pagination import find_next_page_url

logger = logging.getLogger("pyscrappy.generic")


class GenericScraper(BaseScraper):
    """Scrape any URL and extract structured data automatically.

    This is the all-in-one scraper. Point it at any URL and it extracts:
    metadata, main text, links, images, and tables.

    Usage::

        from pyscrappy import GenericScraper

        with GenericScraper() as scraper:
            # Basic: scrape a single page
            result = scraper.scrape(url="https://example.com")
            print(result.data[0]["metadata"]["title"])
            print(result.data[0]["text"]["word_count"])

            # With custom selectors
            result = scraper.scrape(
                url="https://example.com/products",
                selectors={"name": "h2.product-title", "price": "span.price"},
            )

            # With pagination
            result = scraper.scrape(
                url="https://example.com/articles?page=1",
                max_pages=5,
            )

            # Force JS rendering
            result = scraper.scrape(
                url="https://spa-site.com",
                render_js=True,
            )
    """

    name = "generic"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)
        self._metadata_extractor = MetadataExtractor()
        self._text_extractor = TextExtractor()
        self._link_extractor = LinkExtractor()
        self._image_extractor = ImageExtractor()
        self._table_extractor = TableExtractor()

    def scrape(  # type: ignore[override]
        self,
        url: str,
        selectors: dict[str, str] | None = None,
        max_pages: int = 1,
        render_js: bool | None = None,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Scrape one or more pages from a URL.

        Args:
            url: The URL to scrape.
            selectors: Optional dict mapping field names to CSS selectors.
                When provided, each page yields one item per matched element
                group instead of the default full-page extraction.
            max_pages: Maximum number of pages to follow via pagination.
            render_js: Force JS rendering (True), skip it (False),
                or use the config default (None).
            scroll_pages: Number of scroll-downs for infinite-scroll pages
                (only used when rendering JS).

        Returns:
            ScrapeResult with extracted data.
        """
        use_js = render_js if render_js is not None else self.config.render_js

        all_data: list[dict[str, Any]] = []
        all_errors: list[ScrapeError] = []
        visited: list[str] = []
        current_url: str | None = url

        for page_num in range(1, max_pages + 1):
            if current_url is None:
                break

            logger.info("Scraping page %d: %s", page_num, current_url)
            visited.append(current_url)

            try:
                html = self._fetch_with_js_detection(current_url, use_js, scroll_pages)
            except Exception as exc:
                all_errors.append(ScrapeError(url=current_url, message=str(exc)))
                break

            soup = self.parse_html(html)

            if selectors:
                items = self._extract_with_selectors(soup, selectors, current_url)
                all_data.extend(items)
            else:
                page_data = self._extract_all(soup, current_url)
                all_data.append(page_data)

            # Find next page
            if page_num < max_pages:
                current_url = find_next_page_url(soup, current_url)
            else:
                current_url = None

        return ScrapeResult(
            data=all_data,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=all_errors,
        )

    def _fetch_with_js_detection(
        self, url: str, render_js: bool | str, scroll_pages: int
    ) -> str:
        """Fetch HTML, auto-detecting if JS rendering is needed."""
        if render_js is True:
            return self.browser.get_html(url, scroll_pages=scroll_pages)

        # Fetch with plain HTTP first
        html = self.http.get_html(url)

        if render_js == "auto" and self._looks_like_js_rendered(html):
            logger.info("Page appears JS-rendered, falling back to browser")
            return self.browser.get_html(url, scroll_pages=scroll_pages)

        return html

    def _looks_like_js_rendered(self, html: str) -> bool:
        """Heuristic: detect pages that need JS to render content."""
        soup = BeautifulSoup(html, "lxml")
        body = soup.find("body")
        if not body:
            return True

        body_text = body.get_text(strip=True)

        # Very little text content but has script tags
        if len(body_text) < 200 and len(soup.find_all("script")) > 3:
            return True

        # Common SPA markers
        spa_markers = [
            "window.__NEXT_DATA__",
            "window.__NUXT__",
            "__INITIAL_STATE__",
            "root.render(",
            "ReactDOM.render(",
        ]
        html_lower = html[:5000]
        if any(marker in html_lower for marker in spa_markers):
            # But only if the body is mostly empty
            if len(body_text) < 500:
                return True

        # <div id="root"> or <div id="app"> with no meaningful children
        for div_id in ("root", "app", "__next"):
            div = soup.find("div", id=div_id)
            if div and len(div.get_text(strip=True)) < 100:
                return True

        return False

    def _extract_all(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """Run all extractors on a page."""
        return {
            "url": url,
            "metadata": self._metadata_extractor.extract(soup, url),
            "text": self._text_extractor.extract(soup),
            "links": self._link_extractor.extract(soup, url),
            "images": self._image_extractor.extract(soup, url),
            "tables": self._table_extractor.extract(soup),
        }

    def _extract_with_selectors(
        self,
        soup: BeautifulSoup,
        selectors: dict[str, str],
        url: str,
    ) -> list[dict[str, Any]]:
        """Extract data using user-provided CSS selectors.

        If a selector matches multiple elements, each match becomes a row.
        All selectors' results are zipped together.
        """
        columns: dict[str, list[str]] = {}
        max_len = 0

        for field_name, css_selector in selectors.items():
            matches = soup.select(css_selector)
            values = [el.get_text(strip=True) for el in matches]
            columns[field_name] = values
            max_len = max(max_len, len(values))

        # Zip into list of dicts, padding shorter columns with ""
        items: list[dict[str, Any]] = []
        for i in range(max_len):
            row: dict[str, Any] = {"_source_url": url}
            for field_name, values in columns.items():
                row[field_name] = values[i] if i < len(values) else ""
            items.append(row)

        return items
