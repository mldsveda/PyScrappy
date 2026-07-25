"""Currency exchange-rate scraper (via the open.er-api.com API).

Uses the free ExchangeRate-API open endpoint (no key required).
"""

from __future__ import annotations

import json

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_API = "https://open.er-api.com/v6/latest/{base}"


class CurrencyScraper(BaseScraper):
    """Fetch currency exchange rates.

    Usage::

        with CurrencyScraper() as scraper:
            # All rates for a base currency
            result = scraper.scrape(base="USD")

            # Convert an amount to specific currencies
            result = scraper.scrape(base="USD", to="EUR,GBP,JPY", amount=100)
    """

    name = "currency"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        base: str = "USD",
        to: str | None = None,
        amount: float = 1.0,
    ) -> ScrapeResult:
        """Fetch exchange rates for a base currency.

        Args:
            base: Base currency code, e.g. ``"USD"``.
            to: Comma-separated target codes to filter to (e.g. ``"EUR,GBP"``).
                If omitted, returns all available rates.
            amount: Amount of the base currency to convert (default 1).

        Returns:
            ScrapeResult with one row per target currency (code, rate, converted).
        """
        url = _API.format(base=base.upper())

        try:
            payload = json.loads(self.http.get_html(url))
        except Exception as exc:
            return self._err(url, str(exc))

        if payload.get("result") != "success":
            msg = payload.get("error-type", "Unknown currency or API error.")
            return self._err(url, str(msg))

        rates = payload.get("rates", {})
        wanted = (
            {c.strip().upper() for c in to.split(",") if c.strip()} if to else None
        )
        updated = payload.get("time_last_update_utc")

        rows = []
        for code, rate in rates.items():
            if wanted and code not in wanted:
                continue
            rows.append({
                "base": base.upper(),
                "currency": code,
                "rate": rate,
                "amount": amount,
                "converted": round(rate * amount, 4),
                "updated": updated,
            })

        errors = (
            [] if rows
            else [ScrapeError(url=url, message="No matching currencies.")]
        )
        return ScrapeResult(
            data=rows,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _err(self, url: str, message: str) -> ScrapeResult:
        return ScrapeResult(
            data=[],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=[ScrapeError(url=url, message=message)],
        )
