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
