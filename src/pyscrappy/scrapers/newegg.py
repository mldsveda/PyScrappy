"""Newegg product search scraper.

Newegg serves search results as static HTML and is reliably scrapable with a
browser-like header set (no proxy required). Focused on electronics and tech
hardware.
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class NeweggScraper(BaseScraper):
    """Search Newegg products.

    Usage::

        with NeweggScraper() as scraper:
            result = scraper.scrape(query="graphics card", max_pages=2)
            df = result.to_dataframe()
    """

    name = "newegg"

    # A browser-like header set; Newegg is lenient but a bare UA can be throttled.
    _HEADERS = {
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Referer": "https://www.google.com/",
    }

    def __init__(
        self,
        config: ScraperConfig | None = None,
        domain: str = "www.newegg.com",
    ) -> None:
        super().__init__(config)
        self._domain = domain

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Search for products on Newegg.

        Args:
            query: Search query string.
            max_pages: Number of result pages to scrape.

        Returns:
            ScrapeResult with product data (title, price, rating, image, url).
        """
        products: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []

        for page in range(1, max_pages + 1):
            url = (
                f"https://{self._domain}/p/pl?"
                f"d={query.replace(' ', '+')}&page={page}"
            )
            visited.append(url)

            try:
                soup = self.fetch_and_parse(url, headers=self._HEADERS)
            except Exception as exc:
                errors.append(ScrapeError(url=url, message=str(exc)))
                break

            page_products = self._parse_search_results(soup)
            if not page_products:
                break
            products.extend(page_products)

        if not products and not errors:
            errors.append(ScrapeError(
                url=visited[-1] if visited else "",
                message=(
                    "No products extracted. Newegg may have changed its page "
                    "layout, or the query returned no results."
                ),
            ))

        return ScrapeResult(
            data=products,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=errors,
        )

    def _parse_search_results(self, soup: Any) -> list[dict[str, Any]]:
        """Parse product cards from a search results page."""
        products: list[dict[str, Any]] = []
        for cell in soup.select(".item-cell"):
            product = self._parse_product_card(cell)
            if product.get("title"):
                products.append(product)
        return products

    def _parse_product_card(self, cell: Tag) -> dict[str, Any]:
        """Extract product data from a single item cell."""
        product: dict[str, Any] = {}

        title_el = cell.select_one(".item-title")
        if title_el:
            product["title"] = title_el.get_text(strip=True)

        link = cell.select_one("a.item-title")
        if link:
            href = str(link.get("href", ""))
            if href:
                product["url"] = href.split("?")[0]

        # Price: "$669.99–" style; keep the primary amount.
        price_el = cell.select_one(".price-current")
        if price_el:
            price_text = price_el.get_text(strip=True)
            match = re.search(r"\$[\d,]+(?:\.\d{2})?", price_text)
            if match:
                product["price"] = match.group(0)

        # Shipping
        ship_el = cell.select_one(".price-ship")
        if ship_el:
            product["shipping"] = ship_el.get_text(strip=True)

        # Rating (from the aria-label / title on the rating element)
        rating_el = cell.select_one(".item-rating")
        if rating_el:
            label = rating_el.get("aria-label") or rating_el.get("title") or ""
            match = re.search(r"(\d+\.?\d*)", str(label))
            if match:
                product["rating"] = match.group(1)

        # Review count
        review_el = cell.select_one(".item-rating-num")
        if review_el:
            product["review_count"] = review_el.get_text(strip=True).strip("()")

        img = cell.select_one(".item-img img")
        if img:
            product["image"] = img.get("src", "")

        return product
