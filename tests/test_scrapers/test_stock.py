"""Tests for pyscrappy.scrapers.stock."""

import json
from unittest.mock import MagicMock

import pytest

from pyscrappy.core.exceptions import NetworkError
from pyscrappy.core.models import ScrapeResult
from pyscrappy.scrapers.stock import StockScraper

QUOTE_JSON = {
    "chart": {
        "result": [{
            "meta": {
                "symbol": "AAPL",
                "currency": "USD",
                "exchangeName": "NMS",
                "regularMarketPrice": 175.50,
                "chartPreviousClose": 174.20,
                "regularMarketVolume": 50000000,
                "regularMarketDayHigh": 176.00,
                "regularMarketDayLow": 173.80,
                "fiftyTwoWeekHigh": 199.62,
                "fiftyTwoWeekLow": 124.17,
            }
        }]
    }
}

HISTORY_JSON = {
    "chart": {
        "result": [{
            "timestamp": [1704067200, 1704153600],
            "indicators": {
                "quote": [{
                    "open": [185.0, 186.0],
                    "high": [186.5, 187.0],
                    "low": [184.0, 185.5],
                    "close": [186.0, 186.5],
                    "volume": [40000000, 35000000],
                }]
            }
        }]
    }
}

PROFILE_JSON = {
    "chart": {
        "result": [{
            "meta": {
                "symbol": "AAPL",
                "longName": "Apple Inc.",
                "shortName": "Apple",
                "currency": "USD",
                "exchangeName": "NMS",
                "market": "us_market",
                "exchangeTimezoneName": "America/New_York",
                "instrumentType": "EQUITY",
            }
        }]
    }
}


def _mock_http_for_stock(json_data):
    mock_http = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_data
    mock_response.text = "some_crumb"
    mock_response.cookies = {}
    mock_http.get_raw.return_value = mock_response
    return mock_http


class TestStockScraperInit:
    def test_name(self):
        scraper = StockScraper()
        assert scraper.name == "stock"

    def test_initial_state(self):
        scraper = StockScraper()
        assert scraper._crumb is None
        assert scraper._cookies == {}


class TestStockScraperQuote:
    def test_scrape_quote(self):
        scraper = StockScraper()
        scraper._http = _mock_http_for_stock(QUOTE_JSON)

        result = scraper.scrape(symbol="AAPL", mode="quote")

        assert isinstance(result, ScrapeResult)
        assert len(result.data) == 1
        assert result.data[0]["symbol"] == "AAPL"
        assert result.data[0]["currency"] == "USD"
        assert result.data[0]["price"] == 175.50
        assert result.data[0]["volume"] == 50000000
        assert result.metadata.scraper == "stock"
        scraper.close()

    def test_symbol_uppercased(self):
        scraper = StockScraper()
        scraper._http = _mock_http_for_stock(QUOTE_JSON)

        scraper.scrape(symbol="aapl")
        # The symbol should be uppercased before use
        call_url = scraper._http.get_raw.call_args_list[-1][0][0]
        assert "AAPL" in call_url
        scraper.close()


class TestStockScraperHistory:
    def test_scrape_history(self):
        scraper = StockScraper()
        scraper._http = _mock_http_for_stock(HISTORY_JSON)

        result = scraper.scrape(symbol="AAPL", mode="history", period="1mo")

        assert len(result.data) == 2
        assert result.data[0]["open"] == 185.0
        assert result.data[0]["close"] == 186.0
        assert result.data[0]["volume"] == 40000000
        assert "date" in result.data[0]
        scraper.close()

    def test_history_url_params(self):
        scraper = StockScraper()
        scraper._http = _mock_http_for_stock(HISTORY_JSON)

        scraper.scrape(symbol="TSLA", mode="history", period="3mo", interval="1wk")

        call_url = scraper._http.get_raw.call_args_list[-1][0][0]
        assert "TSLA" in call_url
        assert "range=3mo" in call_url
        assert "interval=1wk" in call_url
        scraper.close()


class TestStockScraperProfile:
    def test_scrape_profile(self):
        scraper = StockScraper()
        scraper._http = _mock_http_for_stock(PROFILE_JSON)

        result = scraper.scrape(symbol="AAPL", mode="profile")

        assert len(result.data) == 1
        assert result.data[0]["symbol"] == "AAPL"
        assert result.data[0]["name"] == "Apple Inc."
        assert result.data[0]["exchange"] == "NMS"
        assert result.data[0]["instrument_type"] == "EQUITY"
        scraper.close()


class TestStockScraperEmptyResult:
    def test_empty_chart_result(self):
        scraper = StockScraper()
        scraper._http = _mock_http_for_stock({"chart": {"result": []}})

        result = scraper.scrape(symbol="INVALID")
        assert result.data == []
        scraper.close()


class TestStockScraperCrumb:
    def test_ensure_crumb_fetches_once(self):
        scraper = StockScraper()
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "test_crumb_value"
        mock_response.cookies = {"A": "cookie1"}
        mock_response.json.return_value = QUOTE_JSON
        mock_http.get_raw.return_value = mock_response
        scraper._http = mock_http

        scraper._ensure_crumb()

        assert scraper._crumb == "test_crumb_value"
        assert "A" in scraper._cookies
        scraper.close()

    def test_ensure_crumb_skips_if_already_set(self):
        scraper = StockScraper()
        scraper._crumb = "existing"
        mock_http = MagicMock()
        scraper._http = mock_http

        scraper._ensure_crumb()

        mock_http.get_raw.assert_not_called()
        scraper.close()


class TestStockScraperAppendCrumb:
    def test_append_crumb_with_existing_params(self):
        scraper = StockScraper()
        scraper._crumb = "abc123"
        result = scraper._append_crumb("https://api.com?range=1d")
        assert result == "https://api.com?range=1d&crumb=abc123"

    def test_append_crumb_without_params(self):
        scraper = StockScraper()
        scraper._crumb = "abc123"
        result = scraper._append_crumb("https://api.com")
        assert result == "https://api.com?crumb=abc123"

    def test_append_crumb_no_crumb(self):
        scraper = StockScraper()
        scraper._crumb = None
        result = scraper._append_crumb("https://api.com")
        assert result == "https://api.com"
