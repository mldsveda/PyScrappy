"""Stock market data scraper using Yahoo Finance JSON endpoints."""

from __future__ import annotations

import time
from typing import Any

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult

_YF_BASE = "https://query1.finance.yahoo.com"


class StockScraper(BaseScraper):
    """Scrape stock market data from Yahoo Finance.

    Uses Yahoo Finance's JSON API endpoints instead of brittle HTML scraping.

    Usage::

        with StockScraper() as scraper:
            # Get a stock quote
            result = scraper.scrape(symbol="AAPL")

            # Historical data
            result = scraper.scrape(symbol="AAPL", mode="history", period="1mo")

            # Company profile
            result = scraper.scrape(symbol="AAPL", mode="profile")
    """

    name = "stock"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)
        self._crumb: str | None = None
        self._cookies: dict[str, str] = {}

    def scrape(  # type: ignore[override]
        self,
        symbol: str,
        mode: str = "quote",
        period: str = "1mo",
        interval: str = "1d",
    ) -> ScrapeResult:
        """Scrape stock data.

        Args:
            symbol: Stock ticker symbol (e.g. ``"AAPL"``, ``"GOOGL"``).
            mode: Data type to fetch:
                - ``"quote"``: Current price, volume, market cap, etc.
                - ``"history"``: Historical OHLCV data.
                - ``"profile"``: Company info, sector, employees.
            period: Time period for history (``"1d"``, ``"5d"``, ``"1mo"``,
                ``"3mo"``, ``"6mo"``, ``"1y"``, ``"5y"``, ``"max"``).
            interval: Data interval for history (``"1d"``, ``"1wk"``, ``"1mo"``).

        Returns:
            ScrapeResult with stock data.
        """
        symbol = symbol.upper().strip()

        if mode == "history":
            return self._scrape_history(symbol, period, interval)
        elif mode == "profile":
            return self._scrape_profile(symbol)
        else:
            return self._scrape_quote(symbol)

    def _scrape_quote(self, symbol: str) -> ScrapeResult:
        """Fetch current quote data via the v8 finance endpoint."""
        url = f"{_YF_BASE}/v8/finance/chart/{symbol}?range=1d&interval=1d"
        data = self._fetch_json(url)

        result_data: list[dict[str, Any]] = []
        chart = data.get("chart", {}).get("result", [])
        if chart:
            meta = chart[0].get("meta", {})
            result_data.append({
                "symbol": meta.get("symbol", symbol),
                "currency": meta.get("currency", ""),
                "exchange": meta.get("exchangeName", ""),
                "price": meta.get("regularMarketPrice"),
                "previous_close": meta.get("chartPreviousClose"),
                "volume": meta.get("regularMarketVolume"),
                "day_high": meta.get("regularMarketDayHigh"),
                "day_low": meta.get("regularMarketDayLow"),
                "fifty_two_week_high": meta.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": meta.get("fiftyTwoWeekLow"),
            })

        return ScrapeResult(
            data=result_data,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _scrape_history(
        self, symbol: str, period: str, interval: str
    ) -> ScrapeResult:
        """Fetch historical OHLCV data."""
        url = (
            f"{_YF_BASE}/v8/finance/chart/{symbol}"
            f"?range={period}&interval={interval}"
        )
        data = self._fetch_json(url)

        result_data: list[dict[str, Any]] = []
        chart = data.get("chart", {}).get("result", [])
        if chart:
            timestamps = chart[0].get("timestamp", [])
            indicators = chart[0].get("indicators", {})
            quotes = indicators.get("quote", [{}])[0] if indicators.get("quote") else {}

            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            volumes = quotes.get("volume", [])

            for i, ts in enumerate(timestamps):
                result_data.append({
                    "date": time.strftime("%Y-%m-%d", time.gmtime(ts)),
                    "open": opens[i] if i < len(opens) else None,
                    "high": highs[i] if i < len(highs) else None,
                    "low": lows[i] if i < len(lows) else None,
                    "close": closes[i] if i < len(closes) else None,
                    "volume": volumes[i] if i < len(volumes) else None,
                })

        return ScrapeResult(
            data=result_data,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _scrape_profile(self, symbol: str) -> ScrapeResult:
        """Fetch company profile data."""
        url = f"{_YF_BASE}/v8/finance/chart/{symbol}?range=1d&interval=1d"
        data = self._fetch_json(url)

        result_data: list[dict[str, Any]] = []
        chart = data.get("chart", {}).get("result", [])
        if chart:
            meta = chart[0].get("meta", {})
            result_data.append({
                "symbol": meta.get("symbol", symbol),
                "name": meta.get("longName", meta.get("shortName", "")),
                "currency": meta.get("currency", ""),
                "exchange": meta.get("exchangeName", ""),
                "market": meta.get("market", ""),
                "timezone": meta.get("exchangeTimezoneName", ""),
                "instrument_type": meta.get("instrumentType", ""),
            })

        return ScrapeResult(
            data=result_data,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _ensure_crumb(self) -> None:
        """Obtain a crumb + session cookie from Yahoo Finance.

        Yahoo requires a valid crumb token sent as a query parameter,
        along with session cookies obtained from the consent/finance page.
        """
        if self._crumb:
            return

        # Step 1: Hit the finance page to get consent cookies
        resp = self.http.get_raw("https://finance.yahoo.com/quote/AAPL/")
        for name, value in resp.cookies.items():
            self._cookies[name] = value

        # Step 2: Get crumb using those cookies
        crumb_resp = self.http.get_raw(
            f"{_YF_BASE}/v1/test/getcrumb",
            cookies=self._cookies,
        )
        if crumb_resp.status_code == 200:
            crumb = crumb_resp.text.strip()
            if crumb and len(crumb) < 50:
                self._crumb = crumb
                self.logger.debug("Obtained Yahoo Finance crumb")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        """Fetch JSON from Yahoo Finance with crumb authentication and retry."""
        self._ensure_crumb()

        for attempt in range(self.config.max_retries):
            fetch_url = self._append_crumb(url)
            resp = self.http.get_raw(fetch_url, cookies=self._cookies)

            if resp.status_code == 200:
                try:
                    return resp.json()
                except Exception as exc:
                    raise NetworkError(f"Failed to parse JSON from {url}") from exc

            # Auth expired — refresh crumb and retry
            if resp.status_code in (401, 403):
                self._crumb = None
                self._cookies = {}
                self._ensure_crumb()
                continue

            # Rate-limited — back off and retry
            if resp.status_code == 429:
                delay = self.config.retry_delay * (2 ** attempt)
                self.logger.warning("Rate-limited by Yahoo Finance, retrying in %.1fs", delay)
                time.sleep(delay)
                continue

            raise NetworkError(f"Yahoo Finance returned HTTP {resp.status_code} for {url}")

        raise NetworkError(f"Failed to fetch {url} after {self.config.max_retries} attempts")

    def _append_crumb(self, url: str) -> str:
        if not self._crumb:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}crumb={self._crumb}"
