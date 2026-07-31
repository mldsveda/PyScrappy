"""Tests for proxy rotation and scraping-API service support."""

from unittest.mock import MagicMock

import httpx
import pytest

from pyscrappy.core import scraper_api
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.http import HttpClient


class TestProxyRotation:
    def test_no_proxy(self):
        assert ScraperConfig().pick_proxy() is None

    def test_single_proxy(self):
        cfg = ScraperConfig(proxy="http://host:8080")
        assert cfg.pick_proxy() == "http://host:8080"

    def test_rotating_proxy_picks_from_list(self):
        proxies = ["http://a:1", "http://b:2", "http://c:3"]
        cfg = ScraperConfig(proxy=proxies)
        picks = {cfg.pick_proxy() for _ in range(50)}
        assert picks.issubset(set(proxies))
        assert len(picks) > 1  # actually rotates (probabilistically)

    def test_proxy_reaches_httpx_transport(self):
        cfg = ScraperConfig(proxy="http://127.0.0.1:9")
        client = HttpClient(cfg)
        httpx_client = client._build_client()
        # httpx records proxy-mounted transports
        assert httpx_client._mounts
        httpx_client.close()


class TestScraperApiBuild:
    def test_scraperapi(self):
        endpoint, params = scraper_api.build_request(
            "https://ebay.com/x", {"provider": "scraperapi", "api_key": "K"}
        )
        assert endpoint == "https://api.scraperapi.com/"
        assert params == {"api_key": "K", "url": "https://ebay.com/x"}

    def test_render_js_flag(self):
        _, params = scraper_api.build_request(
            "https://x", {"provider": "scraperapi", "api_key": "K", "render_js": True}
        )
        assert params["render"] == "true"

    def test_scrapeops_and_scrapingbee(self):
        for provider, host in [
            ("scrapeops", "proxy.scrapeops.io"),
            ("scrapingbee", "app.scrapingbee.com"),
        ]:
            endpoint, params = scraper_api.build_request(
                "https://x", {"provider": provider, "api_key": "K"}
            )
            assert host in endpoint
            assert params["api_key"] == "K"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown scraper_api provider"):
            scraper_api.build_request("https://x", {"provider": "nope", "api_key": "K"})

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="api_key is required"):
            scraper_api.build_request("https://x", {"provider": "scraperapi"})

    def test_is_configured(self):
        assert scraper_api.is_configured({"provider": "scraperapi", "api_key": "K"})
        assert not scraper_api.is_configured(None)
        assert not scraper_api.is_configured({"provider": "scraperapi"})  # no key


class TestScraperApiRouting:
    def _client(self, cfg):
        client = HttpClient(cfg)
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.text = "<html>ok</html>"
        resp.raise_for_status = MagicMock()
        mock = MagicMock()
        mock.get.return_value = resp
        client._client = mock
        return client, mock

    def test_routes_through_service(self):
        cfg = ScraperConfig(scraper_api={"provider": "scraperapi", "api_key": "K"}, rate_limit=0)
        client, mock = self._client(cfg)
        client.get_html("https://ebay.com/sch", params={"q": "laptop"})
        call = mock.get.call_args
        assert call[0][0] == "https://api.scraperapi.com/"
        assert call[1]["params"]["url"] == "https://ebay.com/sch?q=laptop"
        assert call[1]["params"]["api_key"] == "K"
        client.close()

    def test_no_service_hits_target_directly(self):
        client, mock = self._client(ScraperConfig(rate_limit=0))
        client.get_html("https://example.com", params={"q": "x"})
        assert mock.get.call_args[0][0] == "https://example.com"
        client.close()
