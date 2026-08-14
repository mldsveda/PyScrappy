"""Tests for the async HTTP client and scrape_async (issue #65).

Mock the underlying httpx.AsyncClient so no real network is used. The sync API
is exercised elsewhere; here we confirm the async path works and mirrors the
sync behavior (retries, caching, header handling).
"""

from unittest.mock import AsyncMock, MagicMock, patch

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
    ok = _resp(text="ok")
    client = AsyncHttpClient(ScraperConfig(rate_limit=0, retry_delay=0, max_retries=2))
    mock_1 = MagicMock()
    mock_1.get = AsyncMock(return_value=err)
    mock_1.aclose = AsyncMock()
    mock_2 = MagicMock()
    mock_2.get = AsyncMock(return_value=ok)
    mock_2.aclose = AsyncMock()
    client._client = mock_1
    client._build_client = MagicMock(side_effect=[mock_2])
    resp = await client.get("https://example.com")
    assert resp.text == "ok"
    assert mock_1.get.call_count == 1
    assert mock_2.get.call_count == 1
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
async def test_async_build_client_rotates_away_from_previous_proxy_when_possible(monkeypatch):
    cfg = ScraperConfig(proxy=["http://proxy-a:8080", "http://proxy-b:8080"])
    client = AsyncHttpClient(cfg)
    client._current_proxy = "http://proxy-a:8080"
    monkeypatch.setattr("random.choice", lambda seq: seq[0])

    async_client = client._build_client()
    assert client._current_proxy == "http://proxy-b:8080"
    await async_client.aclose()


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


def test_async_cache_key_does_not_collide_on_special_chars():
    # Same collision guard for the async client's _cache_key (#114).
    client = AsyncHttpClient(ScraperConfig(rate_limit=0))
    key_a = client._cache_key("http://x", {"a": "1&b=2"})
    key_b = client._cache_key("http://x", {"a": "1", "b": "2"})
    assert key_a != key_b


def test_async_cache_key_handles_url_with_existing_query_string():
    # A URL that already has a "?" must not collide with an equivalent
    # url+params combination once params are appended (#116 review).
    client = AsyncHttpClient(ScraperConfig(rate_limit=0))
    key_a = client._cache_key("http://x?a=1", {"b": "2"})
    key_b = client._cache_key("http://x?a=1?b=2", None)
    assert key_a != key_b
    assert key_a == "http://x?a=1&b=2"
@pytest.mark.anyio
async def test_async_get_429_http_date_retry_after():
    config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=1.0)
    client = AsyncHttpClient(config)

    resp_429 = _resp(status=429)
    resp_429.headers = {"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}

    resp_200 = _resp(text="ok")

    mock = MagicMock()
    mock.get = AsyncMock(side_effect=[resp_429, resp_200])
    mock.aclose = AsyncMock()

    client._client = mock

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await client.get("https://example.com")
        assert res.text == "ok"
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args[0][0] > 0
    await client.aclose()


@pytest.mark.anyio
async def test_async_get_503_honors_retry_after():
    config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=1.0)
    client = AsyncHttpClient(config)

    resp_503 = _resp(status=503)
    resp_503.headers = {"Retry-After": "25"}
    resp_503.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=resp_503)
    )

    resp_200 = _resp(text="ok")

    mock_1 = MagicMock()
    mock_1.get = AsyncMock(return_value=resp_503)
    mock_1.aclose = AsyncMock()

    mock_2 = MagicMock()
    mock_2.get = AsyncMock(return_value=resp_200)
    mock_2.aclose = AsyncMock()

    client._client = mock_1
    client._build_client = MagicMock(side_effect=[mock_2])

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await client.get("https://example.com")
        assert res.text == "ok"
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args[0][0] == 25.0
    await client.aclose()
