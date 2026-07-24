"""Alibaba product search scraper."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class AlibabaScraper(BaseScraper):
    """Scrape product listings from Alibaba.

    Usage::

        with AlibabaScraper() as scraper:
            result = scraper.scrape(query="bluetooth speaker", max_pages=2)
            df = result.to_dataframe()
    """

    name = "alibaba"

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Search for products on Alibaba.

        Args:
            query: Search query string.
            max_pages: Number of result pages to scrape.

        Returns:
            ScrapeResult with product data (name, price, min_order, rating, supplier).
        """
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")

        products: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []

        for page in range(1, max_pages + 1):
            url = (
                f"https://www.alibaba.com/trade/search?"
                f"SearchText={quote_plus(query)}&page={page}"
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

        if not products and not errors:
            errors.append(ScrapeError(
                url=visited[-1] if visited else "",
                message=(
                    "No products extracted. Alibaba blocks automated traffic "
                    "and renders results with JavaScript; a proxy or "
                    "residential IP is typically required."
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

    def _parse_results(self, soup: Any) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []

        for card in soup.select(
            ".organic-gallery-offer-outter, "
            ".m-gallery-product-item-v2, "
            "[class*='offer-card'], "
            ".J-offer-wrapper"
        ):
            product = self._parse_card(card)
            if product and product.get("name"):
                products.append(product)

        return products

    def _parse_card(self, card: Tag) -> dict[str, Any]:
        product: dict[str, Any] = {}

        # Product name
        title_el = card.select_one(
            "h2.title, "
            ".elements-title-normal__content, "
            "[class*='title'] a, "
            "a[title]"
        )
        if title_el:
            product["name"] = (
                title_el.get("title")
                or title_el.get_text(strip=True)
            )

        # URL
        link = card.select_one("a[href*='alibaba.com']") or card.select_one("a[href]")
        if link:
            href = str(link.get("href", ""))
            if href.startswith("//"):
                href = "https:" + href
            product["url"] = href

        # Price
        price_el = card.select_one(
            ".elements-offer-price-normal, "
            "[class*='price'], "
            ".gallery-offer-price"
        )
        if price_el:
            product["price"] = price_el.get_text(strip=True)

        # Minimum order
        moq_el = card.select_one(
            ".element-offer-minorder-normal, "
            "[class*='min-order'], "
            "[class*='moq']"
        )
        if moq_el:
            product["min_order"] = moq_el.get_text(strip=True)

        # Rating
        rating_el = card.select_one(
            ".seb-supplier-review__rating, "
            "[class*='rating']"
        )
        if rating_el:
            product["rating"] = rating_el.get_text(strip=True)

        # Supplier name
        supplier_el = card.select_one(
            ".seb-supplier, "
            "[class*='supplier'] a, "
            "[class*='company']"
        )
        if supplier_el:
            product["supplier"] = supplier_el.get_text(strip=True)

        return product
