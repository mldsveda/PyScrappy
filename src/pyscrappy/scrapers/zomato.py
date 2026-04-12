"""Zomato restaurant scraper."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote_plus

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class ZomatoScraper(BaseScraper):
    """Scrape restaurant listings from Zomato.

    .. note::

        Zomato is heavily JS-rendered. Use ``render_js=True``
        for best results.

    Usage::

        with ZomatoScraper() as scraper:
            result = scraper.scrape(city="bangalore", render_js=True)
            df = result.to_dataframe()
    """

    name = "zomato"

    def scrape(  # type: ignore[override]
        self,
        city: str,
        query: str | None = None,
        max_results: int = 50,
        render_js: bool = False,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Scrape restaurants from Zomato.

        Args:
            city: City name (e.g. ``"bangalore"``, ``"mumbai"``).
            query: Optional cuisine or restaurant search query.
            max_results: Maximum number of restaurants to return.
            render_js: Use browser for JS rendering (recommended).
            scroll_pages: Number of scrolls for loading more content.

        Returns:
            ScrapeResult with restaurant data (name, cuisine, price, rating, address).
        """
        city_slug = city.lower().replace(" ", "-")

        if query:
            url = f"https://www.zomato.com/{city_slug}/search?q={quote_plus(query)}"
        else:
            url = f"https://www.zomato.com/{city_slug}/delivery"

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
                message="No restaurants extracted. Zomato requires JS rendering — use render_js=True.",
            ))

        return ScrapeResult(
            data=restaurants,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _extract_restaurants(
        self, html: str, max_results: int
    ) -> list[dict[str, Any]]:
        """Extract restaurant data from Zomato HTML."""
        # Try embedded JSON first
        json_data = self._extract_from_next_data(html, max_results)
        if json_data:
            return json_data

        # Fallback: parse rendered HTML
        soup = self.parse_html(html)
        restaurants: list[dict[str, Any]] = []

        for card in soup.select(
            "[class*='jumbo-tracker'], "
            "div[data-testid='restaurant-card'], "
            "a[href*='/order/'], "
            "a[href*='/restaurant/']"
        ):
            restaurant = self._parse_card(card)
            if restaurant and restaurant.get("name"):
                restaurants.append(restaurant)
            if len(restaurants) >= max_results:
                break

        return restaurants

    def _parse_card(self, card: Tag) -> dict[str, Any]:
        restaurant: dict[str, Any] = {}

        # Name
        name_el = card.select_one("h4, h3, [class*='res_title']")
        if name_el:
            restaurant["name"] = name_el.get_text(strip=True)

        # URL
        link = card.select_one("a[href*='/order/'], a[href*='/restaurant/']") or (
            card if card.name == "a" else None
        )
        if link:
            href = str(link.get("href", ""))
            if href.startswith("/"):
                href = "https://www.zomato.com" + href
            restaurant["url"] = href

        # Rating
        rating_el = card.select_one(
            "[class*='rating'], "
            "[class*='Rating']"
        )
        if rating_el:
            text = rating_el.get_text(strip=True)
            if text and text[0].isdigit():
                restaurant["rating"] = text

        # Cuisine
        cuisine_el = card.select_one("[class*='cuisine'], p[class*='sc-']")
        if cuisine_el:
            restaurant["cuisine"] = cuisine_el.get_text(strip=True)

        # Price
        price_el = card.select_one("[class*='cost'], [class*='price']")
        if price_el:
            restaurant["price"] = price_el.get_text(strip=True)

        # Delivery time
        time_el = card.select_one("[class*='deliveryTime'], [class*='time']")
        if time_el:
            restaurant["delivery_time"] = time_el.get_text(strip=True)

        return restaurant

    def _extract_from_next_data(
        self, html: str, max_results: int
    ) -> list[dict[str, Any]]:
        """Extract from Zomato's embedded page data."""
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
        """Recursively find restaurant objects in Zomato's JSON."""
        if len(results) >= max_results:
            return

        if isinstance(data, dict):
            # Zomato nests restaurant data in various structures
            info = data.get("info") or data.get("restaurant") or data
            if isinstance(info, dict) and info.get("name") and (
                info.get("cuisine_string") or info.get("cuisines")
            ):
                cuisines = info.get("cuisine_string", "")
                if not cuisines and info.get("cuisines"):
                    cuisines = ", ".join(
                        c.get("name", "") for c in info["cuisines"]
                        if isinstance(c, dict)
                    )
                results.append({
                    "name": info.get("name", ""),
                    "cuisine": cuisines,
                    "rating": info.get("rating", {}).get("aggregate_rating")
                    if isinstance(info.get("rating"), dict)
                    else info.get("rating"),
                    "price": info.get("average_cost_for_two") or info.get("cfo", {}).get("text", ""),
                    "address": info.get("location", {}).get("address", "")
                    if isinstance(info.get("location"), dict) else "",
                    "url": f"https://www.zomato.com/restaurant/{info.get('id', '')}",
                })
                return

            for value in data.values():
                if isinstance(value, (dict, list)):
                    self._find_restaurants(value, results, max_results)

        elif isinstance(data, list):
            for item in data:
                self._find_restaurants(item, results, max_results)
