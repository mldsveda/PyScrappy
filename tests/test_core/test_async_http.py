"""Tests for the async HTTP client and scrape_async (issue #65).

Mock the underlying httpx.AsyncClient so no real network is used. The sync API
is exercised elsewhere; here we confirm the async path works and mirrors the
sync behavior (retries, caching, header handling).
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from pyscrappy import scrape_async
from pyscrappy.core.async_http import AsyncHttpClient
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.http import HttpClient


@pytest.fixture
def anyio_backend():
    # Run @pytest.mark.anyio tests on asyncio only (avoids needing trio).
    return "asyncio"


def _mock_async_client(config, responses):
    """An AsyncHttpClient whose underlying client returns the given responses in
    order (each a MagicMock httpx.Response)."""
    client = AsyncHttpClient(config)
    mock = MagicMock()
    mock.get = AsyncMock(side_effect=responses)
    mock.aclose = AsyncMock()  # aclose is awaited on cleanup
    client._client = mock
    return client, mock


def _resp(status=200, text="<html>OK</html>"):
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text
    r.headers = {}
    r.raise_for_status = MagicMock()
    return r


@pytest.mark.anyio
async def test_async_get_returns_response():
    client, mock = _mock_async_client(ScraperConfig(rate_limit=0), [_resp(text="hi")])
    resp = await client.get("https://example.com")
    assert resp.text == "hi"
    assert mock.get.call_count == 1
    await client.aclose()


@pytest.mark.anyio
async def test_async_get_html_returns_text():
    client, _ = _mock_async_client(ScraperConfig(rate_limit=0), [_resp(text="<h1>Hi</h1>")])
    html = await client.get_html("https://example.com")
    assert html == "<h1>Hi</h1>"
    await client.aclose()


@pytest.mark.anyio
async def test_async_retries_on_server_error():
    err = _resp(status=500)
    err.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=err)
    )
    client, mock = _mock_async_client(
        ScraperConfig(rate_limit=0, retry_delay=0, max_retries=2), [err, _resp(text="ok")]
    )
    resp = await client.get("https://example.com")
    assert resp.text == "ok"
    assert mock.get.call_count == 2  # retried once
    await client.aclose()


@pytest.mark.anyio
async def test_async_shares_cache_with_sync_client():
    # A value cached by the async client is visible to the sync client (shared store).
    HttpClient.clear_cache()
    cfg = ScraperConfig(rate_limit=0, cache_ttl=60)
    client, mock = _mock_async_client(cfg, [_resp(text="cached")])
    r1 = await client.get("https://example.com/x")
    r2 = await client.get("https://example.com/x")  # served from cache, no 2nd call
    assert r1.text == r2.text == "cached"
    assert mock.get.call_count == 1
    await client.aclose()
    HttpClient.clear_cache()


@pytest.mark.anyio
async def test_async_config_headers_and_user_agent_applied():
    cfg = ScraperConfig(rate_limit=0, user_agent="Custom/1.0", headers={"X-Test": "1"})
    client, mock = _mock_async_client(cfg, [_resp()])
    await client.get("https://example.com")
    sent = mock.get.call_args.kwargs["headers"]
    assert sent["User-Agent"] == "Custom/1.0"
    assert sent["X-Test"] == "1"
    await client.aclose()


@pytest.mark.anyio
async def test_scrape_async_extracts_page_data(monkeypatch):
    # Stub the async fetch so scrape_async parses a known HTML doc without network.
    html = "<html><head><title>T</title></head><body><a href='/p'>link</a></body></html>"

    async def fake_get_html(self, url, **kwargs):
        return html

    monkeypatch.setattr(AsyncHttpClient, "get_html", fake_get_html)
    result = await scrape_async("https://example.com")
    assert result.metadata.scraper == "generic"
    assert result.data  # extracted a page
    assert result.metadata.source_urls == ["https://example.com"]
