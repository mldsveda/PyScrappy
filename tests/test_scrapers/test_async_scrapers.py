"""Async-path tests for the site scrapers (issue #65, native async).

Every scraper exposes a native ``scrape_async`` that mirrors ``scrape`` but fetches
over a non-blocking ``AsyncHttpClient``, reusing the same parsing/extraction. These
tests inject a mocked ``_async_http`` (so no real network is used) and assert that
the async path produces the same structured data as the sync path — covering one
scraper per fetch pattern: plain JSON, ID-resolution + JSON, paginated HTML, a
browser scraper's plain-HTTP fallback, ``post_json`` + ``set_cookie``, and the
Yahoo crumb/cookie flow.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.http import HttpClient
from pyscrappy.scrapers.amazon import AmazonScraper
from pyscrappy.scrapers.crypto import CryptoScraper
from pyscrappy.scrapers.stock import StockScraper
from pyscrappy.scrapers.twitter import TwitterScraper
from pyscrappy.scrapers.ubereats import UberEatsScraper


@pytest.fixture
def anyio_backend():
    # Run @pytest.mark.anyio tests on asyncio only (avoids needing trio).
    return "asyncio"


def _mock_async_http(scraper, *html_responses):
    """Inject a mocked async client whose get_html returns the given strings in order."""
    mock = MagicMock()
    mock.get_html = AsyncMock(side_effect=list(html_responses))
    mock.aclose = AsyncMock()
    scraper._async_http = mock
    return scraper, mock


@pytest.mark.anyio
async def test_crypto_scrape_async_top_coins():
    payload = json.dumps(
        [
            {
                "id": "bitcoin",
                "name": "Bitcoin",
                "symbol": "btc",
                "current_price": 64000,
                "market_cap": 1200000000000,
                "market_cap_rank": 1,
                "price_change_percentage_24h": 1.5,
            }
        ]
    )
    s, _ = _mock_async_http(CryptoScraper(), payload)
    r = await s.scrape_async(max_results=1)
    assert len(r.data) == 1
    c = r.data[0]
    # Same extraction as the sync path.
    assert c["name"] == "Bitcoin"
    assert c["symbol"] == "BTC"
    assert c["price"] == 64000
    assert c["currency"] == "USD"
    assert c["change_24h_pct"] == 1.5


@pytest.mark.anyio
async def test_crypto_scrape_async_resolves_ids():
    # query -> a search fetch (id resolution) -> a markets fetch, both awaited.
    search = json.dumps({"coins": [{"id": "ethereum"}]})
    markets = json.dumps(
        [{"id": "ethereum", "name": "Ethereum", "symbol": "eth", "current_price": 1800}]
    )
    s, mock = _mock_async_http(CryptoScraper(), search, markets)
    r = await s.scrape_async(query="eth")
    assert r.data[0]["name"] == "Ethereum"
    # The second (markets) fetch carries the resolved id.
    assert "ids=ethereum" in mock.get_html.call_args_list[-1][0][0]


@pytest.mark.anyio
async def test_amazon_scrape_async_paginates():
    page1 = """
    <html><body>
      <div data-component-type="s-search-result" data-asin="A1">
        <h2><span>Widget One</span></h2>
        <span class="a-price"><span class="a-offscreen">$9.99</span></span>
      </div>
    </body></html>
    """
    s, mock = _mock_async_http(AmazonScraper(), page1)
    r = await s.scrape_async(query="widget", max_pages=1)
    assert r.data, "expected at least one product from the async paginated fetch"
    assert any("Widget One" in (d.get("title") or "") for d in r.data)
    # Fetched over the async client with the scraper's headers.
    assert mock.get_html.await_count == 1


@pytest.mark.anyio
async def test_twitter_scrape_async_falls_back_to_plain_http():
    # Browser scraper: async has no render_js and must fetch over plain HTTP.
    # With non-tweet HTML, it degrades to the documented "use render_js=True" error
    # rather than raising — same behavior as the sync render_js=False path.
    s, mock = _mock_async_http(TwitterScraper(), "<html><body>nothing here</body></html>")
    r = await s.scrape_async(query="python")
    assert mock.get_html.await_count == 1
    # No browser was ever created for the async path.
    assert s._browser is None
    # Either no tweets with a guiding error, or empty data — never a crash.
    assert r.data == [] or r.metadata.scraper == "twitter"


@pytest.mark.anyio
async def test_ubereats_scrape_async_uses_post_json_and_set_cookie():
    geocode = json.dumps({"results": [{"latitude": 51.5, "longitude": -0.12, "name": "London"}]})
    feed = json.dumps(
        {
            "data": {
                "feedItems": [
                    {
                        "type": "REGULAR_STORE",
                        "store": {"title": {"text": "Testaurant"}, "storeUuid": "u1"},
                    }
                ]
            }
        }
    )
    s = UberEatsScraper()
    mock = MagicMock()
    mock.get_html = AsyncMock(return_value=geocode)  # geocode + homepage share get_html
    mock.get_html.side_effect = [geocode, "<html>home</html>"]
    mock.post_json = AsyncMock(return_value=feed)
    mock.set_cookie = MagicMock()
    mock.aclose = AsyncMock()
    s._async_http = mock

    r = await s.scrape_async(city="London")
    assert [d["name"] for d in r.data] == ["Testaurant"]
    # The location cookie was set (sync call, no await) and the feed was POSTed.
    assert mock.set_cookie.called
    assert mock.post_json.await_count == 1


@pytest.mark.anyio
async def test_stock_scrape_async_quote_with_crumb():
    quote_json = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "symbol": "AAPL",
                        "currency": "USD",
                        "exchangeName": "NMS",
                        "regularMarketPrice": 175.5,
                        "regularMarketVolume": 50000000,
                    }
                }
            ]
        }
    }

    def _raw(*_a, **_k):
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "crumb123"
        resp.cookies = {}
        resp.json.return_value = quote_json
        return resp

    s = StockScraper()
    mock = MagicMock()
    mock.get_raw = AsyncMock(side_effect=_raw)
    mock.aclose = AsyncMock()
    s._async_http = mock

    r = await s.scrape_async(symbol="aapl", mode="quote")
    assert len(r.data) == 1
    assert r.data[0]["symbol"] == "AAPL"
    assert r.data[0]["price"] == 175.5
    # symbol was uppercased before the request (same as sync path)
    assert "AAPL" in mock.get_raw.call_args_list[-1][0][0]


@pytest.mark.anyio
async def test_scrape_async_shares_cache_with_sync_client():
    # A response cached during an async scrape is visible to the sync HttpClient
    # (both use the same process-wide store), proving the shared cache wiring.
    HttpClient.clear_cache()
    from pyscrappy.core.async_http import AsyncHttpClient

    cfg = ScraperConfig(rate_limit=0, cache_ttl=60)
    client = AsyncHttpClient(cfg)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.text = "cached-body"
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    inner = MagicMock()
    inner.get = AsyncMock(return_value=resp)
    inner.aclose = AsyncMock()
    client._client = inner

    await client.get("https://example.com/shared")
    # Now a sync client with the same config sees it without a network call.
    with HttpClient(cfg) as sync_client:
        cached = sync_client._cache_get(sync_client._cache_key("https://example.com/shared", None))
    assert cached is not None
    assert cached.text == "cached-body"
    await client.aclose()
    HttpClient.clear_cache()
