"""Uber Eats restaurant scraper (by city).

Uber Eats renders its feed client-side but is backed by a JSON API
(``getFeedV1``). This scraper reaches it directly, without a browser:

1. geocode the city name to coordinates (via Open-Meteo's free geocoder),
2. establish a session (homepage sets cookies),
3. set the ``uev2.loc`` location cookie so the feed knows where to search,
4. POST ``getFeedV1`` and parse the ``REGULAR_STORE`` feed items.

:meth:`get_menu` fetches a single store's menu from the ``schema.org`` JSON-LD
block embedded in the store page (stable SEO markup, not fragile page JS).

No API key required.
"""

from __future__ import annotations

import html as _html
import json
import re
from typing import Any
from urllib.parse import quote, quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
_FEED = "https://www.ubereats.com/_p/api/getFeedV1?localeCode={locale}"

# The cacheKey the web app sends for a default delivery HOME feed.
_CACHE_KEY = "/DELIVERY///0/0//JTVCJTVE/undefined//////HOME////////"


class UberEatsScraper(BaseScraper):
    """Search Uber Eats restaurants available in a city.

    Usage::

        with UberEatsScraper() as scraper:
            result = scraper.scrape(city="London")
            for r in result.data:
                print(r["name"], r.get("eta"), r.get("delivery_fee"))

        # A different Uber Eats locale:
        with UberEatsScraper(locale="us") as scraper:
            result = scraper.scrape(city="Chicago")
    """

    name = "ubereats"

    def __init__(
        self,
        config: ScraperConfig | None = None,
        locale: str = "gb",
    ) -> None:
        super().__init__(config)
        self.locale = locale

    def scrape(  # type: ignore[override]
        self,
        city: str,
        max_results: int = 50,
    ) -> ScrapeResult:
        """List restaurants available for delivery in a city.

        Args:
            city: City name, e.g. ``"London"`` or ``"Chicago"``.
            max_results: Maximum restaurants to return.

        Returns:
            ScrapeResult with restaurant data (name, delivery_fee, eta, url).
        """
        lat, lng, place = self._geocode(city)
        if lat is None:
            return self._err(_GEOCODE, f"City {city!r} not found.")

        # 1. Session cookies from the homepage. Uber Eats has no "/us" path
        #    (US lives at the bare domain); other locales use "/<locale>".
        #    Fetching the bare domain works everywhere and redirects as needed.
        home = "https://www.ubereats.com/"
        try:
            self.http.get_html(home)
        except Exception as exc:
            return self._err(home, str(exc))

        # 2. Location cookie so the feed searches the right place.
        loc = {
            "address": {"title": place or city},
            "latitude": lat,
            "longitude": lng,
            "type": "google_places",
            "source": "manual_auto_complete",
        }
        self.http.set_cookie("uev2.loc", quote(json.dumps(loc)), domain=".ubereats.com")

        # 3. Query the feed API.
        feed_url = _FEED.format(locale=self.locale)
        headers = {
            "x-csrf-token": "x",
            "content-type": "application/json",
            "Origin": "https://www.ubereats.com",
            "Referer": "https://www.ubereats.com/feed",
            "x-uber-target-location-latitude": str(lat),
            "x-uber-target-location-longitude": str(lng),
        }
        body = {
            "cacheKey": _CACHE_KEY,
            "feedSessionCount": {"announcementCount": 0, "announcementLabel": ""},
            "userQuery": "",
            "sortAndFilters": [],
        }

        try:
            raw = self.http.post_json(feed_url, headers=headers, json=body)
            payload = json.loads(raw)
        except Exception as exc:
            return self._err(feed_url, str(exc))

        return self._build_feed_result(payload, feed_url, place, city, max_results)

    async def scrape_async(  # type: ignore[override]
        self,
        city: str,
        max_results: int = 50,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` (same args/returns)."""
        lat, lng, place = await self._geocode_async(city)
        if lat is None:
            return self._err(_GEOCODE, f"City {city!r} not found.")

        home = "https://www.ubereats.com/"
        try:
            await self.async_http.get_html(home)
        except Exception as exc:
            return self._err(home, str(exc))

        loc = {
            "address": {"title": place or city},
            "latitude": lat,
            "longitude": lng,
            "type": "google_places",
            "source": "manual_auto_complete",
        }
        self.async_http.set_cookie("uev2.loc", quote(json.dumps(loc)), domain=".ubereats.com")

        feed_url = _FEED.format(locale=self.locale)
        headers = {
            "x-csrf-token": "x",
            "content-type": "application/json",
            "Origin": "https://www.ubereats.com",
            "Referer": "https://www.ubereats.com/feed",
            "x-uber-target-location-latitude": str(lat),
            "x-uber-target-location-longitude": str(lng),
        }
        body = {
            "cacheKey": _CACHE_KEY,
            "feedSessionCount": {"announcementCount": 0, "announcementLabel": ""},
            "userQuery": "",
            "sortAndFilters": [],
        }

        try:
            raw = await self.async_http.post_json(feed_url, headers=headers, json=body)
            payload = json.loads(raw)
        except Exception as exc:
            return self._err(feed_url, str(exc))

        return self._build_feed_result(payload, feed_url, place, city, max_results)

    def _build_feed_result(
        self,
        payload: dict[str, Any],
        feed_url: str,
        place: str | None,
        city: str,
        max_results: int,
    ) -> ScrapeResult:
        """Shared feed-payload handling for the sync and async scrape paths."""
        data = payload.get("data", {})
        stores = [
            self._parse(fi["store"])
            for fi in data.get("feedItems", [])
            if fi.get("type") == "REGULAR_STORE" and isinstance(fi.get("store"), dict)
        ]
        stores = stores[:max_results]

        errors: list[ScrapeError] = []
        if not stores:
            if data.get("isInServiceArea") is False:
                message = (
                    f"Uber Eats does not deliver to {place or city!r} "
                    "(outside its service area, or not operating in this country)."
                )
            else:
                message = (
                    "No restaurants returned. Uber Eats may not deliver to this "
                    "exact location, or its feed API changed."
                )
            errors.append(ScrapeError(url=feed_url, message=message))

        return ScrapeResult(
            data=stores,
            metadata=ScrapeMetadata(
                source_urls=[feed_url],
                scraper=self.name,
            ),
            errors=errors,
        )

    def get_menu(self, store_url: str) -> ScrapeResult:
        """Fetch a single store's menu.

        Args:
            store_url: A store page URL (from a ``scrape`` result's ``url``),
                e.g. ``"https://www.ubereats.com/gb/store/.../<uuid>"``.

        Returns:
            ScrapeResult whose ``data`` is one dict: the restaurant details plus
            a ``menu`` list of ``{section, name, description, price, currency}``.
        """
        try:
            html = self.http.get_html(store_url)
        except Exception as exc:
            return self._err(store_url, str(exc))

        restaurant = self._extract_jsonld(html)
        if restaurant is None:
            return self._err(
                store_url,
                "No menu data found. The store page markup may have changed.",
            )

        return ScrapeResult(
            data=[restaurant],
            metadata=ScrapeMetadata(source_urls=[store_url], scraper=self.name),
        )

    @staticmethod
    def _extract_jsonld(html: str) -> dict[str, Any] | None:
        """Parse the store's schema.org Restaurant JSON-LD into a flat record."""
        for block in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
        ):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if data.get("@type") != "Restaurant":
                continue

            rating = data.get("aggregateRating") or {}
            menu: list[dict[str, Any]] = []
            has_menu = data.get("hasMenu") or {}
            sections = has_menu.get("hasMenuSection") if isinstance(has_menu, dict) else None
            for section in sections or []:
                if not isinstance(section, dict):
                    continue
                section_name = section.get("name")
                for item in section.get("hasMenuItem", []) or []:
                    if not isinstance(item, dict):
                        continue
                    offers = item.get("offers") or {}
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    name = item.get("name")
                    desc = item.get("description")
                    menu.append(
                        {
                            "section": section_name,
                            "name": _html.unescape(name) if name else None,
                            "description": _html.unescape(desc) if desc else None,
                            "price": offers.get("price") if isinstance(offers, dict) else None,
                            "currency": (
                                offers.get("priceCurrency") if isinstance(offers, dict) else None
                            ),
                        }
                    )

            record = {
                "name": data.get("name"),
                "cuisine": data.get("servesCuisine"),
                "price_range": data.get("priceRange"),
                "rating": rating.get("ratingValue") if isinstance(rating, dict) else None,
                "rating_count": (rating.get("reviewCount") if isinstance(rating, dict) else None),
                "telephone": data.get("telephone"),
                "menu": menu or None,
            }
            return {k: v for k, v in record.items() if v is not None}
        return None

    def _geocode(self, city: str) -> tuple[float | None, float | None, str | None]:
        url = f"{_GEOCODE}?name={quote_plus(city)}&count=1"
        try:
            results = json.loads(self.http.get_html(url)).get("results") or []
        except Exception:
            return None, None, None
        return self._pick_geocode(results)

    async def _geocode_async(self, city: str) -> tuple[float | None, float | None, str | None]:
        url = f"{_GEOCODE}?name={quote_plus(city)}&count=1"
        try:
            results = json.loads(await self.async_http.get_html(url)).get("results") or []
        except Exception:
            return None, None, None
        return self._pick_geocode(results)

    @staticmethod
    def _pick_geocode(results: list) -> tuple[float | None, float | None, str | None]:
        if not results:
            return None, None, None
        r = results[0]
        return r.get("latitude"), r.get("longitude"), r.get("name")

    def _parse(self, store: dict[str, Any]) -> dict[str, Any]:
        title = store.get("title") or {}
        name = title.get("text") if isinstance(title, dict) else title

        # meta is a list of badges: delivery fee, eta, rating, etc.
        delivery_fee = eta = rating = None
        for m in store.get("meta", []) or []:
            if not isinstance(m, dict):
                continue
            text = m.get("text", "")
            low = text.lower()
            if "delivery" in low or "£" in text or "$" in text:
                delivery_fee = delivery_fee or text
            elif "min" in low:
                eta = eta or text
            elif any(c.isdigit() for c in text) and len(text) <= 4:
                rating = rating or text

        # actionUrl is like "/store/<slug>/<uuid>" without the locale prefix;
        # get_menu needs the locale-qualified URL ("/gb/store/...").
        action = store.get("actionUrl", "")
        url = None
        if action.startswith("/store/") and self.locale:
            url = f"https://www.ubereats.com/{self.locale}{action}"
        elif action.startswith("/"):
            url = f"https://www.ubereats.com{action}"
        elif action:
            url = action

        record = {
            "name": name,
            "delivery_fee": delivery_fee,
            "eta": eta,
            "rating": rating,
            "url": url,
            "store_uuid": store.get("storeUuid"),
        }
        return {k: v for k, v in record.items() if v is not None}

    def _err(self, url: str, message: str) -> ScrapeResult:
        return ScrapeResult(
            data=[],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=[ScrapeError(url=url, message=message)],
        )
