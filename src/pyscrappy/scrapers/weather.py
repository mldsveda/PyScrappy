"""Weather scraper (via the Open-Meteo API).

Uses Open-Meteo's free forecast + geocoding APIs (no key required). You pass a
place name; it's geocoded to coordinates, then the current weather is fetched.
"""

from __future__ import annotations

import json
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST = "https://api.open-meteo.com/v1/forecast"

# Minimal WMO weather-code -> description mapping.
_WMO = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
}


class WeatherScraper(BaseScraper):
    """Current weather for a place, via Open-Meteo.

    Usage::

        with WeatherScraper() as scraper:
            result = scraper.scrape(location="London")
            print(result.data[0])
    """

    name = "weather"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        location: str,
    ) -> ScrapeResult:
        """Fetch current weather for a place name.

        Args:
            location: Place name, e.g. ``"London"`` or ``"Tokyo, Japan"``.

        Returns:
            ScrapeResult with a single weather record.
        """
        geo_url = f"{_GEOCODE}?name={quote_plus(location)}&count=1"

        try:
            geo = json.loads(self.http.get_html(geo_url))
        except Exception as exc:
            return self._err(geo_url, str(exc))

        results = geo.get("results") or []
        if not results:
            return self._err(geo_url, f"Location {location!r} not found.")

        place = results[0]
        fc_url = self._forecast_url(place)

        try:
            fc = json.loads(self.http.get_html(fc_url))
        except Exception as exc:
            return self._err(fc_url, str(exc))

        return self._build_result(place, geo_url, fc_url, fc)

    async def scrape_async(  # type: ignore[override]
        self,
        location: str,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` (same args/returns)."""
        geo_url = f"{_GEOCODE}?name={quote_plus(location)}&count=1"

        try:
            geo = json.loads(await self.async_http.get_html(geo_url))
        except Exception as exc:
            return self._err(geo_url, str(exc))

        results = geo.get("results") or []
        if not results:
            return self._err(geo_url, f"Location {location!r} not found.")

        place = results[0]
        fc_url = self._forecast_url(place)

        try:
            fc = json.loads(await self.async_http.get_html(fc_url))
        except Exception as exc:
            return self._err(fc_url, str(exc))

        return self._build_result(place, geo_url, fc_url, fc)

    @staticmethod
    def _forecast_url(place: dict) -> str:
        lat, lon = place.get("latitude"), place.get("longitude")
        return (
            f"{_FORECAST}?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,"
            "wind_speed_10m,weather_code"
        )

    def _build_result(
        self,
        place: dict,
        geo_url: str,
        fc_url: str,
        fc: dict,
    ) -> ScrapeResult:
        """Build the weather ScrapeResult from a forecast payload (shared)."""
        current = fc.get("current") or {}
        units = fc.get("current_units") or {}
        code = current.get("weather_code")
        record = {
            "location": place.get("name"),
            "country": place.get("country"),
            "latitude": place.get("latitude"),
            "longitude": place.get("longitude"),
            "time": current.get("time"),
            "temperature": current.get("temperature_2m"),
            "temperature_unit": units.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_speed_unit": units.get("wind_speed_10m"),
            "condition": _WMO.get(code, "Unknown") if code is not None else None,
        }
        record = {k: v for k, v in record.items() if v is not None}

        return ScrapeResult(
            data=[record],
            metadata=ScrapeMetadata(source_urls=[geo_url, fc_url], scraper=self.name),
        )

    def _err(self, url: str, message: str) -> ScrapeResult:
        return ScrapeResult(
            data=[],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=[ScrapeError(url=url, message=message)],
        )
