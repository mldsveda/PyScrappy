"""Snapdeal product search scraper."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class SnapdealScraper(BaseScraper):
    """Scrape product listings from Snapdeal.

    Usage::

        with SnapdealScraper() as scraper:
            result = scraper.scrape(query="headphones", max_pages=2)
            df = result.to_dataframe()
    """

    name = "snapdeal"

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Search for products on Snapdeal.

        Args:
            query: Search query string.
            max_pages: Number of result pages to scrape.

        Returns:
            ScrapeResult with product data (name, price, original_price, rating).
        """
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")

        products: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []

        for page in range(1, max_pages + 1):
            url = (
                f"https://www.snapdeal.com/search?"
                f"keyword={quote_plus(query)}&sort=rlvncy&page={page}"
            )
            visited.append(url)

            try:
                soup = self.fetch_and_parse(url)
            except Exception as exc:
                errors.append(ScrapeError(url=url, message=str(exc)))
                break

            page_products = self._parse_results(soup)
            if not page_products:
                break
            products.extend(page_products)

        return ScrapeResult(
            data=products,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=errors,
        )

    def _parse_results(self, soup: Any) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []

        for card in soup.select(
            ".product-tuple-listing, "
            ".product-tuple-description, "
            ".product-desc-rating"
        ):
            product = self._parse_card(card)
            if product and product.get("name"):
                products.append(product)

        return products

    def _parse_card(self, card: Tag) -> dict[str, Any]:
        product: dict[str, Any] = {}

        # Name
        title_el = card.select_one(".product-title, p.product-title")
        if title_el:
            product["name"] = title_el.get_text(strip=True)

        # URL
        link = card.select_one("a[href]")
        if link:
            href = str(link.get("href", ""))
            if href.startswith("//"):
                href = "https:" + href
            product["url"] = href

        # Current price
        price_el = card.select_one(
            ".lfloat.product-price, "
            "span.product-price"
        )
        if price_el:
            product["price"] = price_el.get_text(strip=True)

        # Original price
        orig_el = card.select_one(
            ".product-desc-price.strike, "
            "span.product-desc-price"
        )
        if orig_el:
            product["original_price"] = orig_el.get_text(strip=True)

        # Rating
        rating_el = card.select_one(
            ".product-rating-count, "
            ".filled-stars"
        )
        if rating_el:
            product["rating"] = rating_el.get_text(strip=True) or rating_el.get("style", "")

        return product
