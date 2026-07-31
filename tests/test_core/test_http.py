"""Tests for pyscrappy.core.http."""

from unittest.mock import MagicMock

import httpx
import pytest

from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError
from pyscrappy.core.http import HttpClient


class TestHttpClientInit:
    def test_default_config(self):
        client = HttpClient()
        assert client.config.timeout == 30.0
        assert client._client is None

    def test_custom_config(self):
        config = ScraperConfig(timeout=10.0, max_retries=5)
        client = HttpClient(config)
        assert client.config.timeout == 10.0
        assert client.config.max_retries == 5


class TestHttpClientContextManager:
    def test_enter_creates_client(self):
        with HttpClient() as client:
            assert client._client is not None
        assert client._client is None

    def test_close_idempotent(self):
        client = HttpClient()
        client.close()  # should not raise even with no client


class TestHttpClientGet:
    def test_get_success(self):
        config = ScraperConfig(max_retries=1, rate_limit=0)
        client = HttpClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "<html>OK</html>"
        mock_response.raise_for_status = MagicMock()

        mock_httpx = MagicMock()
        mock_httpx.get.return_value = mock_response

        client._client = mock_httpx
        resp = client.get("https://example.com")
        assert resp.status_code == 200
        client.close()

    def test_get_html_returns_text(self):
        config = ScraperConfig(max_retries=1, rate_limit=0)
        client = HttpClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "<html>Hello</html>"
        mock_response.raise_for_status = MagicMock()

        mock_httpx = MagicMock()
        mock_httpx.get.return_value = mock_response

        client._client = mock_httpx
        html = client.get_html("https://example.com")
        assert html == "<html>Hello</html>"
        client.close()

    def test_get_raw_does_not_raise_on_non_2xx(self):
        config = ScraperConfig(rate_limit=0)
        client = HttpClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404

        mock_httpx = MagicMock()
        mock_httpx.get.return_value = mock_response

        client._client = mock_httpx
        resp = client.get_raw("https://example.com/404")
        assert resp.status_code == 404
        client.close()

    def test_get_raises_rate_limit_error_on_429(self):
        config = ScraperConfig(max_retries=1, rate_limit=0, retry_delay=0)
        client = HttpClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "0"}

        mock_httpx = MagicMock()
        mock_httpx.get.return_value = mock_response

        client._client = mock_httpx
        with pytest.raises(RateLimitError, match="Rate-limited"):
            client.get("https://example.com")
        client.close()

    def test_get_raises_network_error_on_http_error(self):
        config = ScraperConfig(max_retries=1, rate_limit=0)
        client = HttpClient(config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403

        def raise_for_status():
            raise httpx.HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=mock_response,
            )

        mock_response.raise_for_status = raise_for_status

        mock_httpx = MagicMock()
        mock_httpx.get.return_value = mock_response

        client._client = mock_httpx
        with pytest.raises(NetworkError, match="HTTP 403"):
            client.get("https://example.com")
        client.close()

    def test_get_retries_on_server_error(self):
        config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=0)
        client = HttpClient(config)

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 500

        def raise_500():
            raise httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=error_response,
            )

        error_response.raise_for_status = raise_500

        ok_response = MagicMock(spec=httpx.Response)
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()

        mock_httpx = MagicMock()
        mock_httpx.get.side_effect = [error_response, ok_response]

        client._client = mock_httpx
        resp = client.get("https://example.com")
        assert resp.status_code == 200
        assert mock_httpx.get.call_count == 2
        client.close()

    def test_get_retries_on_request_error(self):
        config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=0)
        client = HttpClient(config)

        ok_response = MagicMock(spec=httpx.Response)
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()

        mock_httpx = MagicMock()
        mock_httpx.get.side_effect = [
            httpx.ConnectError("connection refused"),
            ok_response,
        ]

        client._client = mock_httpx
        resp = client.get("https://example.com")
        assert resp.status_code == 200
        client.close()

    def test_get_exhausts_retries_raises_network_error(self):
        config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=0)
        client = HttpClient(config)

        mock_httpx = MagicMock()
        mock_httpx.get.side_effect = httpx.ConnectError("refused")

        client._client = mock_httpx
        with pytest.raises(NetworkError, match="Failed to fetch"):
            client.get("https://example.com")
        assert mock_httpx.get.call_count == 2
        client.close()


class TestHttpClientRateLimit:
    def test_rate_limit_tracks_domain(self):
        config = ScraperConfig(rate_limit=0)
        client = HttpClient(config)
        client._rate_limit("https://example.com/page1")
        assert "example.com" in client._last_request_time

    def test_different_domains_tracked_separately(self):
        config = ScraperConfig(rate_limit=0)
        client = HttpClient(config)
        client._rate_limit("https://a.com/page")
        client._rate_limit("https://b.com/page")
        assert "a.com" in client._last_request_time
        assert "b.com" in client._last_request_time


class TestHttpClientUserAgentRotation:
    def test_pick_ua_returns_from_config(self):
        config = ScraperConfig(user_agents=["TestAgent/1.0"])
        client = HttpClient(config)
        assert client._pick_ua() == "TestAgent/1.0"

    def test_pick_ua_random_from_list(self):
        agents = ["Agent/1", "Agent/2", "Agent/3"]
        config = ScraperConfig(user_agents=agents)
        client = HttpClient(config)
        picked = {client._pick_ua() for _ in range(50)}
        # At least 2 different agents should be picked in 50 tries
        assert len(picked) >= 2


class TestHttpClientBuildClient:
    def test_build_client_with_proxy(self):
        config = ScraperConfig(proxy="http://proxy:8080", verify_ssl=False)
        client = HttpClient(config)
        httpx_client = client._build_client()
        assert httpx_client is not None
        httpx_client.close()

    def test_build_client_default(self):
        config = ScraperConfig()
        client = HttpClient(config)
        httpx_client = client._build_client()
        assert httpx_client is not None
        httpx_client.close()

    def test_ensure_client_creates_lazily(self):
        client = HttpClient()
        assert client._client is None
        result = client._ensure_client()
        assert result is not None
        assert client._client is result
        client.close()


class TestHttpClientCaching:
    @pytest.fixture(autouse=True)
    def _clear_shared_cache(self):
        # The response cache is process-wide, so isolate each test.
        HttpClient.clear_cache()
        yield
        HttpClient.clear_cache()

    def _mock_client(self, config):
        client = HttpClient(config)
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.text = "<html>OK</html>"
        resp.raise_for_status = MagicMock()
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = resp
        client._client = mock_httpx
        return client, mock_httpx

    def test_disabled_by_default(self):
        client, mock_httpx = self._mock_client(ScraperConfig(rate_limit=0))
        for _ in range(3):
            client.get("https://example.com")
        assert mock_httpx.get.call_count == 3  # no caching
        client.close()

    def test_cache_hit_skips_network(self):
        client, mock_httpx = self._mock_client(ScraperConfig(rate_limit=0, cache_ttl=60))
        for _ in range(3):
            client.get("https://example.com")
        assert mock_httpx.get.call_count == 1  # only first hit the network
        client.close()

    def test_expired_entry_triggers_refetch(self, monkeypatch):
        # Drive a fake clock so the entry ages past its TTL without sleeping.
        import pyscrappy.core.http as http_mod

        now = [1000.0]
        monkeypatch.setattr(http_mod.time, "monotonic", lambda: now[0])

        client, mock_httpx = self._mock_client(ScraperConfig(rate_limit=0, cache_ttl=60))
        client.get("https://example.com")  # network + cache
        now[0] += 30  # within TTL -> served from cache
        client.get("https://example.com")
        assert mock_httpx.get.call_count == 1
        now[0] += 31  # total 61s > 60s TTL -> entry is stale, must re-fetch
        client.get("https://example.com")
        assert mock_httpx.get.call_count == 2
        client.close()

    def test_params_are_part_of_key(self):
        client, mock_httpx = self._mock_client(ScraperConfig(rate_limit=0, cache_ttl=60))
        client.get("https://api.example.com", params={"q": "a"})
        client.get("https://api.example.com", params={"q": "a"})  # cached
        client.get("https://api.example.com", params={"q": "b"})  # new key
        assert mock_httpx.get.call_count == 2
        client.close()

    def test_clear_cache_forces_refetch(self):
        client, mock_httpx = self._mock_client(ScraperConfig(rate_limit=0, cache_ttl=60))
        client.get("https://example.com")
        client.clear_cache()
        client.get("https://example.com")
        assert mock_httpx.get.call_count == 2
        client.close()

    def test_non_2xx_not_cached(self):
        # get_raw bypasses caching entirely; only successful get() responses cache
        client, mock_httpx = self._mock_client(ScraperConfig(rate_limit=0, cache_ttl=60))
        client.get_raw("https://example.com")
        client.get_raw("https://example.com")
        assert mock_httpx.get.call_count == 2
        client.close()
