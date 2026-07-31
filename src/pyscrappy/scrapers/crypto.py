"""Cryptocurrency market data scraper (via the CoinGecko API).

Uses CoinGecko's free public API (no key required).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"
_SEARCH = "https://api.coingecko.com/api/v3/search"


class CryptoScraper(BaseScraper):
    """Fetch cryptocurrency market data via CoinGecko.

    Usage::

        with CryptoScraper() as scraper:
            # Top coins by market cap
            result = scraper.scrape(max_results=10)

            # Specific coins (by name or symbol)
            result = scraper.scrape(query="bitcoin, ethereum")

            # Prices in another currency
            result = scraper.scrape(query="bitcoin", vs_currency="eur")
    """

    name = "crypto"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        query: str | None = None,
        max_results: int = 20,
        vs_currency: str = "usd",
    ) -> ScrapeResult:
        """Fetch coin market data.

        Args:
            query: Comma-separated coin names/symbols (e.g. ``"bitcoin, eth"``).
                If omitted, returns the top coins by market cap.
            max_results: Maximum coins to return.
            vs_currency: Fiat currency for prices (e.g. ``"usd"``, ``"eur"``).

        Returns:
            ScrapeResult with coin data (name, symbol, price, market cap, …).
        """
        ids = self._resolve_ids(query) if query else None
        url = (
            f"{_MARKETS}?vs_currency={vs_currency}"
            f"&order=market_cap_desc&per_page={max_results}&page=1"
        )
        if ids:
            url += f"&ids={quote_plus(','.join(ids))}"

        try:
            payload = json.loads(self.http.get_html(url))
        except Exception as exc:
            return self._err(url, str(exc))

        if not isinstance(payload, list):
            return self._err(url, "Unexpected response from CoinGecko.")

        coins = [self._parse(c, vs_currency) for c in payload if isinstance(c, dict)]
        errors = [] if coins else [ScrapeError(url=url, message="No coins found for this query.")]
        return ScrapeResult(
            data=coins,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _resolve_ids(self, query: str) -> list[str]:
        """Map coin names/symbols to CoinGecko ids via its search endpoint."""
        ids: list[str] = []
        for term in (t.strip() for t in query.split(",") if t.strip()):
            try:
                res = json.loads(self.http.get_html(f"{_SEARCH}?query={quote_plus(term)}"))
                coins = res.get("coins", [])
                if coins:
                    ids.append(coins[0]["id"])
            except Exception:
                continue
        return ids

    @staticmethod
    def _parse(c: dict[str, Any], vs_currency: str) -> dict[str, Any]:
        coin = {
            "name": c.get("name"),
            "symbol": (c.get("symbol") or "").upper() or None,
            "price": c.get("current_price"),
            "currency": vs_currency.upper(),
            "market_cap": c.get("market_cap"),
            "market_cap_rank": c.get("market_cap_rank"),
            "change_24h_pct": c.get("price_change_percentage_24h"),
            "volume_24h": c.get("total_volume"),
            "high_24h": c.get("high_24h"),
            "low_24h": c.get("low_24h"),
        }
        return {k: v for k, v in coin.items() if v is not None}

    def _err(self, url: str, message: str) -> ScrapeResult:
        return ScrapeResult(
            data=[],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=[ScrapeError(url=url, message=message)],
        )
