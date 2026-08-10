"""MCP tools must expose/forward the scraper parameters they document, and only
advertise engines the scrapers actually support."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastmcp")

from pyscrappy.mcp import server  # noqa: E402


@pytest.mark.anyio
async def test_search_hackernews_forwards_tags():
    sig = inspect.signature(server.search_hackernews)
    assert "tags" in sig.parameters
    assert sig.parameters["tags"].default == "story"

    mock_scraper = MagicMock()
    mock_scraper.scrape.return_value = MagicMock(
        data=[],
        metadata=MagicMock(scraper="hackernews", source_urls=[]),
        errors=[],
    )
    mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
    mock_scraper.__exit__ = MagicMock(return_value=False)

    with patch.object(server, "HackerNewsScraper", return_value=mock_scraper):
        await server.search_hackernews(query="python", tags="show_hn")

    kwargs = mock_scraper.scrape.call_args.kwargs
    assert kwargs.get("tags") == "show_hn"


@pytest.mark.anyio
async def test_scrape_stock_forwards_interval():
    sig = inspect.signature(server.scrape_stock)
    assert "interval" in sig.parameters
    assert sig.parameters["interval"].default == "1d"

    mock_scraper = MagicMock()
    mock_scraper.scrape.return_value = MagicMock(
        data=[],
        metadata=MagicMock(scraper="stock", source_urls=[]),
        errors=[],
    )
    mock_scraper.__enter__ = MagicMock(return_value=mock_scraper)
    mock_scraper.__exit__ = MagicMock(return_value=False)

    with patch.object(server, "StockScraper", return_value=mock_scraper):
        await server.scrape_stock(symbol="AAPL", mode="history", period="1mo", interval="1wk")

    kwargs = mock_scraper.scrape.call_args.kwargs
    assert kwargs.get("interval") == "1wk"


def test_search_images_doc_does_not_advertise_duckduckgo():
    doc = server.search_images.__doc__ or ""
    assert "duckduckgo" not in doc.lower()
    assert "bing" in doc.lower()
    assert "google" in doc.lower()


def test_scrape_stock_docstring_fields_match_actual_output():
    """The quote/profile field lists in scrape_stock's docstring must match
    what _build_quote and _build_profile actually return."""
    import re

    from pyscrappy.scrapers.stock import StockScraper

    QUOTE_JSON = {
        "chart": {
            "result": [{
                "meta": {
                    "symbol": "AAPL", "currency": "USD", "exchangeName": "NMS",
                    "regularMarketPrice": 175.50, "chartPreviousClose": 174.20,
                    "regularMarketVolume": 50000000, "regularMarketDayHigh": 176.00,
                    "regularMarketDayLow": 173.80, "fiftyTwoWeekHigh": 199.62,
                    "fiftyTwoWeekLow": 124.17,
                }
            }]
        }
    }
    PROFILE_JSON = {
        "chart": {
            "result": [{
                "meta": {
                    "symbol": "AAPL", "longName": "Apple Inc.", "currency": "USD",
                    "exchangeName": "NMS", "market": "us_market",
                    "exchangeTimezoneName": "America/New_York",
                    "instrumentType": "EQUITY",
                }
            }]
        }
    }

    def _mock_http(json_data):
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json_data
        mock_response.text = "crumb"
        mock_response.cookies = {}
        mock_http.get_raw.return_value = mock_response
        return mock_http

    scraper = StockScraper()
    scraper._http = _mock_http(QUOTE_JSON)
    result = scraper.scrape(symbol="AAPL", mode="quote")
    actual_quote_keys = set(result.data[0].keys())
    scraper.close()

    scraper2 = StockScraper()
    scraper2._http = _mock_http(PROFILE_JSON)
    result2 = scraper2.scrape(symbol="AAPL", mode="profile")
    actual_profile_keys = set(result2.data[0].keys())
    scraper2.close()

    history_result_keys = {"date", "open", "high", "low", "close", "volume"}

    doc = server.scrape_stock.__doc__ or ""
    quote_match = re.search(r'"quote":\s*(\{[^}]+\})', doc)
    profile_match = re.search(r'"profile":\s*(\{[^}]+\})', doc)
    assert quote_match, "docstring missing quote field list"
    assert profile_match, "docstring missing profile field list"

    doc_quote_keys = {k.strip().strip('"') for k in quote_match.group(1).strip("{}").split(",")}
    doc_profile_keys = {k.strip().strip('"') for k in profile_match.group(1).strip("{}").split(",")}

    assert doc_quote_keys == actual_quote_keys, (
        f"docstring quote keys {sorted(doc_quote_keys)} != actual {sorted(actual_quote_keys)}"
    )
    assert doc_profile_keys == actual_profile_keys, (
        f"docstring profile keys {sorted(doc_profile_keys)} != actual {sorted(actual_profile_keys)}"
    )
    # Verify history shape is also listed as expected.
    assert "history" in doc.lower()
    doc_history_match = re.search(r'"rows":\s*\[(\{[^}]+\})', doc)
    assert doc_history_match is not None
    doc_history_keys = {
        k.strip().strip('"') for k in doc_history_match.group(1).strip("{}").split(",")
    }
    assert doc_history_keys == history_result_keys, (
        f"docstring history row keys {sorted(doc_history_keys)} != expected {sorted(history_result_keys)}"
    )
