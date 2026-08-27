"""Tests for pyscrappy.core.http."""

import os
import random
import shutil
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError
from pyscrappy.core.http import HttpClient, backoff_delay, parse_retry_after


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

    def test_module_backoff_delay_shared_by_scrapers(self):
        # The module-level helper (used by scrapers with their own retry loops,
        # e.g. the stock scraper) honors the same config as HttpClient.
        cfg = ScraperConfig(
            retry_delay=1.0,
            backoff_factor=2.0,
            backoff_max=5.0,
            retry_jitter=False,
        )
        assert backoff_delay(cfg, 1) == 1.0
        assert backoff_delay(cfg, 4) == 5.0  # 8.0 capped to 5.0

    def test_backoff_delay_defaults_to_full_jitter_within_capped_bound(self):
        cfg = ScraperConfig(retry_delay=1.0, backoff_factor=2.0, backoff_max=5.0)
        seeded_random = random.Random(7)

        with patch(
            "pyscrappy.core.http.random.uniform", side_effect=seeded_random.uniform
        ) as mock_uniform:
            delays = [backoff_delay(cfg, 4) for _ in range(50)]

        assert len(set(delays)) > 1
        assert all(0.0 <= delay <= 5.0 for delay in delays)
        assert {mock_call.args for mock_call in mock_uniform.call_args_list} == {(0.0, 5.0)}

    def test_backoff_delay_can_disable_jitter(self):
        cfg = ScraperConfig(
            retry_delay=2.0,
            backoff_factor=3.0,
            backoff_max=10.0,
            retry_jitter=False,
        )

        with patch("pyscrappy.core.http.random.uniform") as mock_uniform:
            assert backoff_delay(cfg, 3) == 10.0

        mock_uniform.assert_not_called()

    def test_backoff_delay_defaults_to_exponential_doubling(self):
        client = HttpClient(
            ScraperConfig(retry_delay=1.0, retry_jitter=False)
        )  # factor 2.0 by default
        assert client._backoff_delay(1) == 1.0
        assert client._backoff_delay(2) == 2.0
        assert client._backoff_delay(3) == 4.0
        client.close()

    def test_backoff_factor_is_configurable(self):
        client = HttpClient(ScraperConfig(retry_delay=2.0, backoff_factor=3.0, retry_jitter=False))
        assert client._backoff_delay(1) == 2.0
        assert client._backoff_delay(2) == 6.0
        assert client._backoff_delay(3) == 18.0
        client.close()

    def test_backoff_factor_one_keeps_delay_constant(self):
        client = HttpClient(ScraperConfig(retry_delay=1.5, backoff_factor=1.0, retry_jitter=False))
        assert client._backoff_delay(1) == 1.5
        assert client._backoff_delay(5) == 1.5
        client.close()

    def test_backoff_max_caps_the_delay(self):
        client = HttpClient(
            ScraperConfig(
                retry_delay=1.0,
                backoff_factor=2.0,
                backoff_max=5.0,
                retry_jitter=False,
            )
        )
        assert client._backoff_delay(3) == 4.0  # under the cap
        assert client._backoff_delay(4) == 5.0  # 8.0 clamped to 5.0
        assert client._backoff_delay(10) == 5.0  # stays capped
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

        mock_httpx_1 = MagicMock()
        mock_httpx_1.get.return_value = error_response
        mock_httpx_2 = MagicMock()
        mock_httpx_2.get.return_value = ok_response

        client._client = mock_httpx_1
        client._build_client = MagicMock(side_effect=[mock_httpx_2])
        resp = client.get("https://example.com")
        assert resp.status_code == 200
        assert mock_httpx_1.get.call_count == 1
        assert mock_httpx_2.get.call_count == 1
        client.close()

    def test_get_sleeps_for_the_jittered_backoff(self):
        config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=4.0)
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

        first_client = MagicMock()
        first_client.get.return_value = error_response
        second_client = MagicMock()
        second_client.get.return_value = ok_response
        client._client = first_client
        client._build_client = MagicMock(side_effect=[second_client])

        with patch("pyscrappy.core.http.random.uniform", return_value=1.25) as mock_uniform:
            with patch("time.sleep") as mock_sleep:
                response = client.get("https://example.com")

        assert response.status_code == 200
        mock_uniform.assert_called_once_with(0.0, 4.0)
        mock_sleep.assert_called_once_with(1.25)
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

        mock_httpx_1 = MagicMock()
        mock_httpx_1.get.side_effect = httpx.ConnectError("refused")
        mock_httpx_2 = MagicMock()
        mock_httpx_2.get.side_effect = httpx.ConnectError("refused")

        client._client = mock_httpx_1
        client._build_client = MagicMock(side_effect=[mock_httpx_2])
        with pytest.raises(NetworkError, match="Failed to fetch"):
            client.get("https://example.com")
        assert mock_httpx_1.get.call_count == 1
        assert mock_httpx_2.get.call_count == 1
        client.close()

    def test_get_429_http_date_retry_after(self):
        # retry_delay=0.0 so a positive sleep can only come from actually parsing
        # the HTTP-date header, not from the fallback default.
        config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=0.0)
        client = HttpClient(config)

        # HTTP-date in the future (e.g. +10s)
        resp_429 = MagicMock(spec=httpx.Response)
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}

        resp_200 = MagicMock(spec=httpx.Response)
        resp_200.status_code = 200
        resp_200.raise_for_status = MagicMock()

        mock_httpx = MagicMock()
        mock_httpx.get.side_effect = [resp_429, resp_200]
        client._client = mock_httpx

        with patch("time.sleep") as mock_sleep:
            res = client.get("https://example.com")
            assert res.status_code == 200
            assert mock_sleep.call_count == 1
            assert mock_sleep.call_args[0][0] > 0
        client.close()

    def test_get_503_honors_retry_after(self):
        config = ScraperConfig(max_retries=2, rate_limit=0, retry_delay=1.0)
        client = HttpClient(config)

        resp_503 = MagicMock(spec=httpx.Response)
        resp_503.status_code = 503
        resp_503.headers = {"Retry-After": "15"}

        def raise_503():
            raise httpx.HTTPStatusError(
                "503 Service Unavailable",
                request=MagicMock(),
                response=resp_503,
            )

        resp_503.raise_for_status = raise_503

        resp_200 = MagicMock(spec=httpx.Response)
        resp_200.status_code = 200
        resp_200.raise_for_status = MagicMock()

        mock_httpx_1 = MagicMock()
        mock_httpx_1.get.return_value = resp_503
        mock_httpx_2 = MagicMock()
        mock_httpx_2.get.return_value = resp_200

        client._client = mock_httpx_1
        client._build_client = MagicMock(side_effect=[mock_httpx_2])

        with patch("time.sleep") as mock_sleep:
            res = client.get("https://example.com")
            assert res.status_code == 200
            assert mock_sleep.call_count == 1
            assert mock_sleep.call_args[0][0] == 15.0
        client.close()


class TestParseRetryAfter:
    def test_numeric_delay_seconds(self):
        assert parse_retry_after("120", 5.0) == 120.0
        assert parse_retry_after("0", 5.0) == 0.0

    def test_negative_delay_clamped_to_zero(self):
        assert parse_retry_after("-10", 5.0) == 0.0

    def test_none_or_empty_returns_default(self):
        assert parse_retry_after(None, 5.0) == 5.0
        assert parse_retry_after("", 5.0) == 5.0

    def test_invalid_string_returns_default(self):
        assert parse_retry_after("garbage-header-value", 5.0) == 5.0

    def test_http_date_future(self):
        # 100 seconds in the future
        future_ts = datetime.now(timezone.utc).timestamp() + 100
        future_dt = datetime.fromtimestamp(future_ts, tz=timezone.utc)
        date_str = future_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
        parsed = parse_retry_after(date_str, 5.0)
        assert 90.0 <= parsed <= 110.0


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

    def test_config_user_agent_overrides_rotation(self):
        # A single configured user_agent wins over user_agents rotation.
        config = ScraperConfig(user_agent="Custom/9.9", user_agents=["A", "B", "C"])
        client = HttpClient(config)
        assert {client._pick_ua() for _ in range(20)} == {"Custom/9.9"}


class TestHttpClientCustomHeaders:
    def test_config_headers_are_sent(self):
        config = ScraperConfig(headers={"Accept-Language": "en-US", "X-Test": "1"})
        client = HttpClient(config)
        merged = client._merge_headers({})
        assert merged["Accept-Language"] == "en-US"
        assert merged["X-Test"] == "1"
        assert "User-Agent" in merged

    def test_per_call_headers_override_config(self):
        config = ScraperConfig(headers={"X-Test": "config"})
        client = HttpClient(config)
        merged = client._merge_headers({"X-Test": "call"})
        assert merged["X-Test"] == "call"  # per-call wins

    def test_config_user_agent_flows_through_merge(self):
        config = ScraperConfig(user_agent="Custom/1.0", headers={"X": "y"})
        client = HttpClient(config)
        merged = client._merge_headers({})
        assert merged["User-Agent"] == "Custom/1.0"
        assert merged["X"] == "y"


class TestHttpClientBuildClient:
    def test_build_client_with_proxy(self):
        config = ScraperConfig(proxy="http://proxy:8080", verify_ssl=False)
        client = HttpClient(config)
        httpx_client = client._build_client()
        assert httpx_client is not None
        httpx_client.close()

    def test_build_client_rotates_away_from_previous_proxy_when_possible(self, monkeypatch):
        config = ScraperConfig(proxy=["http://proxy-a:8080", "http://proxy-b:8080"])
        client = HttpClient(config)
        client._current_proxy = "http://proxy-a:8080"
        monkeypatch.setattr("random.choice", lambda seq: seq[0])

        httpx_client = client._build_client()
        assert client._current_proxy == "http://proxy-b:8080"
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

    def test_cache_key_does_not_collide_on_special_chars(self):
        # A value containing & or = must not alias to a different param set (#114).
        client = HttpClient(ScraperConfig(rate_limit=0))
        key_a = client._cache_key("http://x", {"a": "1&b=2"})
        key_b = client._cache_key("http://x", {"a": "1", "b": "2"})
        assert key_a != key_b
        client.close()

    def test_cache_key_handles_url_with_existing_query_string(self):
        # A URL that already has a "?" must not collide with an equivalent
        # url+params combination once params are appended (#116 review).
        client = HttpClient(ScraperConfig(rate_limit=0))
        key_a = client._cache_key("http://x?a=1", {"b": "2"})
        key_b = client._cache_key("http://x?a=1?b=2", None)
        assert key_a != key_b
        assert key_a == "http://x?a=1&b=2"
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

    def test_cache_is_bounded_by_max_size(self):
        # A long-running process that fetches many distinct URLs must not grow the
        # cache without limit: only the last `cache_max_size` entries stay live.
        import pyscrappy.core.http as http_mod

        client, _ = self._mock_client(ScraperConfig(rate_limit=0, cache_ttl=60, cache_max_size=3))
        for i in range(10):
            client.get(f"https://example.com/{i}")
        assert len(http_mod._SHARED_CACHE) == 3
        client.close()

    def test_lru_evicts_least_recently_used(self):
        # Re-reading an entry marks it most-recently-used, so it survives eviction
        # while an untouched neighbour is dropped.
        client, mock_httpx = self._mock_client(
            ScraperConfig(rate_limit=0, cache_ttl=60, cache_max_size=2)
        )
        client.get("https://example.com/a")  # network
        client.get("https://example.com/b")  # network; cache = [a, b]
        client.get("https://example.com/a")  # cache hit; a now MRU, b now LRU
        client.get("https://example.com/c")  # network; evicts b, cache = [a, c]
        assert mock_httpx.get.call_count == 3
        client.get("https://example.com/a")  # still cached -> no network
        assert mock_httpx.get.call_count == 3
        client.get("https://example.com/b")  # evicted -> re-fetch
        assert mock_httpx.get.call_count == 4
        client.close()

    def _disk_mock_client(self, config):
        # like _mock_client but sets real headers/content so the disk cache can
        # serialize dict(resp.headers) and base64(resp.content).
        client, mock = self._mock_client(config)
        resp = mock.get.return_value
        resp.headers = {}
        resp.content = resp.text.encode("utf-8")
        resp.request = httpx.Request("GET", "https://example.com")
        return client, mock

    def test_disk_cache_survives_a_fresh_client(self, tmp_path):
        # The whole point of cache_dir: a hit persists across process restarts.
        # Simulate a restart by clearing the in-memory cache + disk registry.
        import pyscrappy.core.http as http_mod

        cache_dir = str(tmp_path / "httpcache")
        cfg = ScraperConfig(rate_limit=0, cache_ttl=60, cache_dir=cache_dir)

        client, mock = self._disk_mock_client(cfg)
        client.get("https://example.com")
        client.get("https://example.com")
        assert mock.get.call_count == 1  # second served from memory
        client.close()

        # "restart": wipe memory and the shared disk-cache instances.
        http_mod._SHARED_CACHE.clear()
        http_mod._DISK_CACHES.clear()

        client2, mock2 = self._disk_mock_client(cfg)
        resp = client2.get("https://example.com")
        assert mock2.get.call_count == 0  # served from disk, no network
        assert resp.text == "<html>OK</html>"
        client2.close()

    def test_disk_cache_off_by_default(self, tmp_path):
        # No cache_dir => the disk-cache path factory is never invoked (in-memory
        # only). Assert against the registry, not a path the code never used.
        import pyscrappy.core.http as http_mod

        cfg = ScraperConfig(rate_limit=0, cache_ttl=60)
        client, _ = self._disk_mock_client(cfg)
        with patch.object(http_mod, "_disk_cache_for") as disk:
            client.get("https://example.com")
            client.get("https://example.com")  # cache hit, still no disk
        client.close()
        disk.assert_not_called()

    def test_disk_cache_handles_stealth_response_without_request_attr(self, tmp_path):
        # The stealth adapter returns a _StealthResponse (no .request); disk put
        # must not raise on it (best-effort caching, must never break a scrape).
        import pyscrappy.core.http as http_mod
        from pyscrappy.core._stealth import _StealthResponse

        class _FakeRaw:
            text = "ok"
            content = b"ok"
            status_code = 200
            headers = {}
            cookies = {}
            url = "http://x"

        dc = http_mod._DiskCache(str(tmp_path / "sc"))
        dc.put("k", _StealthResponse(_FakeRaw()))  # must not raise
        hit = dc.get("k", 60)
        assert hit is not None and hit.text == "ok"

    def test_disk_cache_for_expands_home(self):
        import pyscrappy.core.http as http_mod

        http_mod._DISK_CACHES.clear()
        a = http_mod._disk_cache_for("~/.cache/pyscrappy_test_expand")
        b = http_mod._disk_cache_for(os.path.expanduser("~/.cache/pyscrappy_test_expand"))
        assert a is b  # ~ and expanded path map to one instance
        assert "~" not in str(a._dir)
        http_mod._DISK_CACHES.clear()

    def test_disk_cache_roundtrips_binary_body_losslessly(self, tmp_path):
        # Body is stored base64 of the raw bytes, so a non-UTF-8 / binary body
        # survives the round-trip intact (re-encoding resp.text would corrupt it).
        import pyscrappy.core.http as http_mod

        binary = bytes(range(256))  # includes invalid-UTF-8 sequences
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.content = binary
        resp.headers = {}
        resp.request = httpx.Request("GET", "http://x")

        dc = http_mod._DiskCache(str(tmp_path / "bin"))
        dc.put("k", resp)
        hit = dc.get("k", 60)
        assert hit is not None
        assert hit.content == binary  # byte-for-byte

    def test_disk_cache_get_bad_entry_is_a_miss(self, tmp_path):
        # A malformed cache file must behave as a miss, never raise.
        import pyscrappy.core.http as http_mod

        dc = http_mod._DiskCache(str(tmp_path / "bad"))
        path = dc._path("k")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not valid json", encoding="utf-8")
        assert dc.get("k", 60) is None

    def test_disk_cache_preserves_duplicate_headers(self, tmp_path):
        # Duplicate headers (e.g. multiple Set-Cookie) must survive the round-trip;
        # dict(headers) would collapse them.
        import pyscrappy.core.http as http_mod

        resp = httpx.Response(
            200,
            headers=[("Set-Cookie", "a=1"), ("Set-Cookie", "b=2"), ("Content-Type", "text/html")],
            content=b"ok",
            request=httpx.Request("GET", "http://x"),
        )
        dc = http_mod._DiskCache(str(tmp_path / "hdr"))
        dc.put("k", resp)
        hit = dc.get("k", 60)
        assert hit is not None
        assert hit.headers.get_list("Set-Cookie") == ["a=1", "b=2"]
        assert hit.headers.get("Content-Type") == "text/html"

    def _disk_resp(self, url):
        return httpx.Response(200, content=b"x", request=httpx.Request("GET", url))

    def test_disk_cache_evicts_oldest_past_max_size(self, tmp_path):
        # #166: an unbounded on-disk cache grows one file per distinct URL
        # forever. put() must cap it, keeping the most recently written entries.
        import pyscrappy.core.http as http_mod

        dc = http_mod._DiskCache(str(tmp_path / "capped"), max_size=5)
        for i in range(20):
            dc.put(f"http://x/{i}", self._disk_resp(f"http://x/{i}"), ttl=100)

        remaining = list((tmp_path / "capped").glob("*.json"))
        assert len(remaining) == 5
        # The 5 most recently written keys are the last 5 (0..19 in order).
        for i in range(15, 20):
            assert dc.get(f"http://x/{i}", 100) is not None
        for i in range(0, 15):
            assert dc.get(f"http://x/{i}", 100) is None

    def test_disk_cache_put_max_size_overrides_the_instance_default(self, tmp_path):
        import pyscrappy.core.http as http_mod

        dc = http_mod._DiskCache(str(tmp_path / "override"))  # default max_size
        for i in range(10):
            dc.put(f"http://x/{i}", self._disk_resp(f"http://x/{i}"), ttl=100, max_size=3)
        assert len(list((tmp_path / "override").glob("*.json"))) == 3

    def test_disk_cache_sweeps_an_expired_entry_even_if_never_reread(self, tmp_path):
        # get()'s lazy expiry only catches a key that is re-requested. put()'s
        # prune must also reap a key that expires and is never asked for again.
        import pyscrappy.core.http as http_mod

        dc = http_mod._DiskCache(str(tmp_path / "sweep"), max_size=100)
        dc.put("http://x/expired", self._disk_resp("http://x/expired"), ttl=0.01)
        time.sleep(0.05)
        dc.put("http://x/other", self._disk_resp("http://x/other"), ttl=0.01)

        remaining = list((tmp_path / "sweep").glob("*.json"))
        assert len(remaining) == 1
        assert dc.get("http://x/other", 0.01) is not None

    def test_disk_cache_prune_failure_does_not_raise(self, tmp_path):
        # A prune that cannot even list the directory (e.g. removed out from
        # under the cache) must behave as a no-op, not break the write it follows.
        import pyscrappy.core.http as http_mod

        cache_dir = tmp_path / "gone"
        dc = http_mod._DiskCache(str(cache_dir), max_size=1)
        dc.put("http://x/a", self._disk_resp("http://x/a"), ttl=100)
        shutil.rmtree(cache_dir)
        dc.put("http://x/b", self._disk_resp("http://x/b"), ttl=100)  # must not raise
