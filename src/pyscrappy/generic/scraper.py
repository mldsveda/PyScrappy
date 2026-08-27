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

    async def scrape_async(
        self,
        url: str,
        selectors: dict[str, str] | None = None,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` for asyncio callers.

        Fetches with a native ``AsyncHttpClient`` (no thread pool) and reuses the
        same synchronous parsing/extraction. JS rendering is not supported here
        (the browser backend is sync-only); use :meth:`scrape` with ``render_js``
        for pages that need a browser.

        Args, Returns: same as :meth:`scrape` (minus render_js/scroll_pages).
        """
        from pyscrappy.core.async_http import AsyncHttpClient

        all_data: list[dict[str, Any]] = []
        all_errors: list[ScrapeError] = []
        visited: list[str] = []
        current_url: str | None = url

        async with AsyncHttpClient(self.config) as http:
            for page_num in range(1, max_pages + 1):
                if current_url is None:
                    break
                logger.info("Scraping page %d (async): %s", page_num, current_url)
                visited.append(current_url)
                try:
                    html = await http.get_html(current_url)
                except Exception as exc:
                    all_errors.append(ScrapeError(url=current_url, message=str(exc)))
                    break

                soup = self.parse_html(html)
                if selectors:
                    all_data.extend(self._extract_with_selectors(soup, selectors, current_url))
                else:
                    all_data.append(self._extract_all(soup, current_url))

                current_url = (
                    find_next_page_url(soup, current_url) if page_num < max_pages else None
                )

        return ScrapeResult(
            data=all_data,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=all_errors,
        )

    def _fetch_with_js_detection(self, url: str, render_js: bool | str, scroll_pages: int) -> str:
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

    # -- sitemap crawling --

    def sitemap_urls(self, url: str, max_urls: int | None = None) -> list[str]:
        """Enumerate a site's page URLs from its sitemap(s).

        Discovers sitemaps from the site's ``robots.txt`` ``Sitemap:`` directives,
        falling back to the conventional ``/sitemap.xml``. Fetches each, parses
        ``<urlset>`` leaves for page URLs and recurses one level into any
        ``<sitemapindex>`` children. gzip-compressed sitemaps are handled. Fetches
        go through the normal HTTP client (rate-limit, cache, proxy, stealth);
        robots checking is skipped for the sitemap/robots files themselves.

        Args:
            url: Any URL on the target site (its host is used to locate sitemaps).
            max_urls: Cap on the number of page URLs returned (None = no cap).

        Returns:
            A de-duplicated list of page URLs, in discovery order, capped to
            ``max_urls``.
        """
        from collections import deque
        from urllib.parse import urljoin

        from pyscrappy.core.robots import get_host_and_robots_url
        from pyscrappy.generic.sitemap import parse_sitemap, sitemaps_from_robots

        _, robots_url = get_host_and_robots_url(url)

        # Fetch robots.txt / sitemaps through the normal client (retry, cache,
        # proxy, rate-limit) but skip the robots *permission* check for these
        # files themselves. get() raises on a non-2xx / missing file; we treat any
        # failure as "this sitemap isn't there" and move on.
        def _fetch(u: str) -> bytes | None:
            try:
                return self.http.get(u, skip_robots_check=True).content
            except Exception:  # noqa: BLE001 - a missing/broken file is skipped
                return None

        # 1. Discover sitemap URLs: robots.txt Sitemap: lines, else /sitemap.xml.
        robots_body = _fetch(robots_url)
        sitemap_queue = (
            sitemaps_from_robots(robots_body.decode(errors="replace")) if robots_body else []
        )
        if not sitemap_queue:
            sitemap_queue = [urljoin(robots_url, "/sitemap.xml")]

        # 2. Fetch + parse. Recurse one level for sitemap-index children.
        page_urls: list[str] = []
        seen_pages: set[str] = set()
        seen_sitemaps: set[str] = set()
        # queue holds (sitemap_url, is_child) so an index only recurses one level.
        # deque so dequeuing is O(1) even with many discovered sitemaps.
        queue: deque[tuple[str, bool]] = deque((s, False) for s in sitemap_queue)
        while queue:
            if max_urls is not None and len(page_urls) >= max_urls:
                break
            sm_url, is_child = queue.popleft()
            if sm_url in seen_sitemaps:
                continue
            seen_sitemaps.add(sm_url)
            data = _fetch(sm_url)
            if data is None:
                continue
            pages, children = parse_sitemap(data)
            for p in pages:
                if p not in seen_pages:
                    seen_pages.add(p)
                    page_urls.append(p)
                    if max_urls is not None and len(page_urls) >= max_urls:
                        break
            if not is_child:  # only descend one level into an index
                queue.extend((c, True) for c in children)

        return page_urls[:max_urls] if max_urls is not None else page_urls

    def scrape_sitemap(
        self,
        url: str,
        max_urls: int = 100,
        selectors: dict[str, str] | None = None,
        render_js: bool | None = None,
        max_workers: int = 8,
    ) -> ScrapeResult:
        """Scrape every page listed in a site's sitemap, concurrently.

        Enumerates URLs via :meth:`sitemap_urls` (capped at ``max_urls``), scrapes
        each with the normal extraction pipeline, and merges everything into one
        :class:`ScrapeResult` (data concatenated, per-URL errors preserved).

        Args:
            url: Any URL on the target site.
            max_urls: Maximum number of pages to scrape (default 100). A sitemap
                can list tens of thousands of URLs, so this is a required guard.
            selectors: Optional CSS selectors, passed through to :meth:`scrape`.
            render_js: JS-render override, passed through to :meth:`scrape`.
            max_workers: Concurrency for the fan-out.

        Returns:
            A single ScrapeResult over all scraped pages.
        """
        from pyscrappy.concurrent import scrape_all

        urls = self.sitemap_urls(url, max_urls=max_urls)
        if not urls:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper="generic:sitemap"),
                errors=[ScrapeError(url=url, message="no sitemap URLs found")],
            )

        # Each page is scraped by its own scraper instance so the concurrent
        # fetches don't share one client's mutable per-request state.
        def _one(page_url: str):
            def _run() -> ScrapeResult:
                with GenericScraper(self.config) as gs:
                    return gs.scrape(page_url, selectors=selectors, render_js=render_js)

            return _run

        results = scrape_all([_one(u) for u in urls], max_workers=max_workers)

        data: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        for r in results:
            data.extend(r.data)
            errors.extend(r.errors)
        return ScrapeResult(
            data=data,
            metadata=ScrapeMetadata(
                source_urls=urls,
                total_pages=len(urls),
                scraper="generic:sitemap",
            ),
            errors=errors,
        )
