"""Flipkart product search scraper."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class FlipkartScraper(BaseScraper):
    """Scrape product listings from Flipkart.

    Usage::

        with FlipkartScraper() as scraper:
            result = scraper.scrape(query="laptop", max_pages=2)
            df = result.to_dataframe()
    """

    name = "flipkart"

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Search for products on Flipkart.

        Args:
            query: Search query string.
            max_pages: Number of result pages to scrape.

        Returns:
            ScrapeResult with product data (name, price, original_price, rating, description).
        """
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")

        products: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []

        for page in range(1, max_pages + 1):
            url = (
                f"https://www.flipkart.com/search?"
                f"q={quote_plus(query)}&page={page}"
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

        # Flipkart uses different card layouts — try multiple selectors
        for card in soup.select(
            "[data-id], "
            "div.tUxRFH, "
            "div.slAVV4, "
            "div.cPHDOP"
        ):
            product = self._parse_card(card)
            if product and product.get("name"):
                products.append(product)

        return products

    def _parse_card(self, card: Tag) -> dict[str, Any]:
        product: dict[str, Any] = {}

        # Product name — Flipkart uses various class patterns
        title_el = card.select_one(
            "a.wjcEIp, "
            "div.KzDlHZ, "
            "a.s1Q9rs, "
            "a[title]"
        )
        if title_el:
            product["name"] = title_el.get("title") or title_el.get_text(strip=True)

        # URL
        link = card.select_one("a[href*='/p/']") or card.select_one("a[href]")
        if link:
            href = str(link.get("href", ""))
            if href.startswith("/"):
                href = "https://www.flipkart.com" + href
            product["url"] = href.split("?")[0]

        # Current price
        price_el = card.select_one(
            "div.Nx9bqj, "
            "div._30jeq3, "
            "div[class*='price']"
        )
        if price_el:
            product["price"] = price_el.get_text(strip=True)

        # Original price (strikethrough)
        orig_el = card.select_one(
            "div.yRaY8j, "
            "div._3I9_wc, "
            "div[class*='strike']"
        )
        if orig_el:
            product["original_price"] = orig_el.get_text(strip=True)

        # Rating
        rating_el = card.select_one(
            "div.XQDdHH, "
            "div._3LWZlK, "
            "span[class*='rating']"
        )
        if rating_el:
            product["rating"] = rating_el.get_text(strip=True)

        # Description / highlights
        desc_el = card.select_one(
            "ul.G4BRas, "
            "div._1xgFaf, "
            "ul[class*='highlight']"
        )
        if desc_el:
            items = [li.get_text(strip=True) for li in desc_el.find_all("li")]
            product["description"] = "; ".join(items) if items else desc_el.get_text(strip=True)

        return product
