"""IKEA product search scraper (via IKEA's JSON search API).

IKEA's website renders products client-side, but it's backed by a public JSON
search endpoint (``sik.search.blue.cdtapps.com``). Querying that directly is
more robust than scraping the rendered HTML and returns clean structured data.
"""

from __future__ import annotations

import json
from typing import Any

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_SEARCH_HOST = "https://sik.search.blue.cdtapps.com"


class IKEAScraper(BaseScraper):
    """Search IKEA products via its JSON search API.

    Usage::

        with IKEAScraper() as scraper:
            result = scraper.scrape(query="desk", max_results=24)
            df = result.to_dataframe()

        # A different country/language store:
        with IKEAScraper(country="gb", lang="en") as scraper:
            result = scraper.scrape(query="bookshelf")
    """

    name = "ikea"

    _HEADERS = {
        "Accept": "application/json",
        "Referer": "https://www.ikea.com/",
    }

    def __init__(
        self,
        config: ScraperConfig | None = None,
        country: str = "us",
        lang: str = "en",
    ) -> None:
        super().__init__(config)
        self.country = country
        self.lang = lang

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 24,
    ) -> ScrapeResult:
        """Search for products on IKEA.

        Args:
            query: Search query string, e.g. ``"desk"``.
            max_results: Maximum number of products to return.

        Returns:
            ScrapeResult with product data (name, type, price, url, image, …).
        """
        url = self._build_url(query, max_results)

        try:
            raw = self.http.get_html(url, headers=self._HEADERS)
            payload = json.loads(raw)
        except Exception as exc:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
                errors=[ScrapeError(url=url, message=str(exc))],
            )

        return self._build_result(payload, url)

    async def scrape_async(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 24,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` (same args/returns)."""
        url = self._build_url(query, max_results)

        try:
            raw = await self.async_http.get_html(url, headers=self._HEADERS)
            payload = json.loads(raw)
        except Exception as exc:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
                errors=[ScrapeError(url=url, message=str(exc))],
            )

        return self._build_result(payload, url)

    def _build_url(self, query: str, max_results: int) -> str:
        """Build the IKEA JSON search-API URL for a query."""
        from urllib.parse import quote_plus

        return (
            f"{_SEARCH_HOST}/{self.country}/{self.lang}/search-result-page"
            f"?q={quote_plus(query)}&size={max_results}&types=PRODUCT"
        )

    def _build_result(self, payload: dict[str, Any], url: str) -> ScrapeResult:
        """Map the search-API payload into a ScrapeResult (shared sync/async)."""
        errors: list[ScrapeError] = []

        items = (
            payload.get("searchResultPage", {}).get("products", {}).get("main", {}).get("items", [])
        )

        products = [
            self._parse_product(item["product"])
            for item in items
            if isinstance(item, dict) and isinstance(item.get("product"), dict)
        ]

        if not products:
            errors.append(
                ScrapeError(
                    url=url,
                    message="No products returned for this query.",
                )
            )

        return ScrapeResult(
            data=products,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    @staticmethod
    def _parse_product(p: dict[str, Any]) -> dict[str, Any]:
        """Map an IKEA API product object to PyScrappy's flat schema."""
        price = p.get("salesPrice") or {}
        product = {
            "name": p.get("name"),
            "type": p.get("typeName"),
            "description": p.get("itemMeasureReferenceText") or p.get("gprDescription"),
            "item_no": p.get("id"),
            "price": price.get("numeral"),
            "currency": (price.get("current") or {}).get("prefix") or price.get("prefix"),
            "url": p.get("pipUrl"),
            "image": p.get("mainImageUrl"),
            "rating": p.get("ratingValue"),
            "review_count": p.get("ratingCount"),
        }
        return {k: v for k, v in product.items() if v is not None}
