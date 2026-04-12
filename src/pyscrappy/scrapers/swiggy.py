"""Swiggy restaurant scraper."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class SwiggyScraper(BaseScraper):
    """Scrape restaurant listings from Swiggy.

    .. note::

        Swiggy is heavily JS-rendered. Use ``render_js=True``
        for best results.

    Usage::

        with SwiggyScraper() as scraper:
            result = scraper.scrape(city="bangalore", render_js=True)
            df = result.to_dataframe()
    """

    name = "swiggy"

    def scrape(  # type: ignore[override]
        self,
        city: str,
        query: str | None = None,
        max_results: int = 50,
        render_js: bool = False,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Scrape restaurants from Swiggy.

        Args:
            city: City name (e.g. ``"bangalore"``, ``"mumbai"``).
            query: Optional search query to filter restaurants.
            max_results: Maximum number of restaurants to return.
            render_js: Use browser for JS rendering (recommended).
            scroll_pages: Number of scrolls for loading more content.

        Returns:
            ScrapeResult with restaurant data (name, cuisine, price, rating, delivery_time).
        """
        if query:
            url = f"https://www.swiggy.com/search?query={quote_plus(query)}"
        else:
            url = f"https://www.swiggy.com/city/{quote_plus(city.lower())}"

        errors: list[ScrapeError] = []

        if render_js:
            html = self.browser.get_html(
                url, wait_for="networkidle", scroll_pages=scroll_pages
            )
        else:
            html = self.http.get_html(url)

        restaurants = self._extract_restaurants(html, max_results)

        if not restaurants:
            errors.append(ScrapeError(
                url=url,
                message="No restaurants extracted. Swiggy requires JS rendering — use render_js=True.",
            ))

        return ScrapeResult(
            data=restaurants,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _extract_restaurants(
        self, html: str, max_results: int
    ) -> list[dict[str, Any]]:
        """Extract restaurant data from Swiggy HTML."""
        restaurants: list[dict[str, Any]] = []

        # Try embedded JSON first (Swiggy uses Next.js)
        json_data = self._extract_from_next_data(html, max_results)
        if json_data:
            return json_data

        # Fallback: parse rendered HTML
        soup = self.parse_html(html)

        for card in soup.select(
            "[data-testid='restaurant-card'], "
            ".sc-aXZVg, "
            "a[href*='/restaurants/']"
        ):
            restaurant = self._parse_card(card)
            if restaurant and restaurant.get("name"):
                restaurants.append(restaurant)
            if len(restaurants) >= max_results:
                break

        return restaurants

    def _parse_card(self, card: Tag) -> dict[str, Any]:
        restaurant: dict[str, Any] = {}

        # Name — usually the first prominent text element
        name_el = card.select_one(
            "[class*='RestaurantName'], "
            "div[class*='name'], "
            "h3, h4"
        )
        if name_el:
            restaurant["name"] = name_el.get_text(strip=True)

        # URL
        link = card.select_one("a[href*='/restaurants/']") or (
            card if card.name == "a" else None
        )
        if link:
            href = str(link.get("href", ""))
            if href.startswith("/"):
                href = "https://www.swiggy.com" + href
            restaurant["url"] = href

        # Rating
        rating_el = card.select_one(
            "[class*='rating'], "
            "[class*='Rating']"
        )
        if rating_el:
            restaurant["rating"] = rating_el.get_text(strip=True)

        # Cuisine
        cuisine_el = card.select_one(
            "[class*='cuisine'], "
            "[class*='Cuisine']"
        )
        if cuisine_el:
            restaurant["cuisine"] = cuisine_el.get_text(strip=True)

        # Price
        price_el = card.select_one(
            "[class*='cost'], "
            "[class*='price'], "
            "[class*='Price']"
        )
        if price_el:
            restaurant["price"] = price_el.get_text(strip=True)

        # Delivery time
        time_el = card.select_one(
            "[class*='delivery'], "
            "[class*='Delivery'], "
            "[class*='time']"
        )
        if time_el:
            restaurant["delivery_time"] = time_el.get_text(strip=True)

        return restaurant

    def _extract_from_next_data(
        self, html: str, max_results: int
    ) -> list[dict[str, Any]]:
        """Extract from Swiggy's __NEXT_DATA__ JSON."""
        import json
        import re

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html, re.DOTALL,
        )
        if not match:
            return []

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        restaurants: list[dict[str, Any]] = []
        self._find_restaurants(data, restaurants, max_results)
        return restaurants

    def _find_restaurants(
        self, data: Any, results: list[dict[str, Any]], max_results: int
    ) -> None:
        """Recursively find restaurant info objects in Swiggy's JSON."""
        if len(results) >= max_results:
            return

        if isinstance(data, dict):
            info = data.get("info", {})
            if isinstance(info, dict) and info.get("name") and info.get("cuisines"):
                results.append({
                    "name": info.get("name", ""),
                    "cuisine": ", ".join(info.get("cuisines", [])),
                    "rating": info.get("avgRating"),
                    "price": info.get("costForTwoMessage", ""),
                    "delivery_time": info.get("sla", {}).get("deliveryTime"),
                    "url": f"https://www.swiggy.com/restaurants/{info.get('id', '')}",
                })
                return

            for value in data.values():
                self._find_restaurants(value, results, max_results)

        elif isinstance(data, list):
            for item in data:
                self._find_restaurants(item, results, max_results)
