"""Tests for robots.txt politeness enforcement and caching."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from pyscrappy.core.async_http import AsyncHttpClient
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import RobotsDisallowedError
from pyscrappy.core.http import HttpClient
from pyscrappy.core.robots import check_robots_sync, get_host_and_robots_url


def test_get_host_and_robots_url():
    host, robots_url = get_host_and_robots_url("https://example.com/some/path?query=1")
    assert host == "example.com"
    assert robots_url == "https://example.com/robots.txt"


def test_obey_robots_disabled_by_default_does_not_fetch_robots():
    config = ScraperConfig(obey_robots=False)

    def fake_httpx_get(url, *args, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.text = "<h1>Hello</h1>"
        resp.headers = {}
        return resp

    with patch("httpx.Client.get", side_effect=fake_httpx_get) as mock_httpx:
        with HttpClient(config) as client:
            client.get("https://example.com/page")

        for call_args in mock_httpx.call_args_list:
            assert "robots.txt" not in str(call_args)


def test_obey_robots_allowed_path():
    robots_txt = """\
User-agent: *
Disallow: /admin/
Allow: /public/
"""
    config = ScraperConfig(obey_robots=True)

    def fake_httpx_get(url, *args, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.headers = {}
        if "robots.txt" in str(url):
            resp.text = robots_txt
        else:
            resp.text = "OK"
        return resp

    with patch("httpx.Client.get", side_effect=fake_httpx_get):
        with HttpClient(config) as client:
            resp = client.get("https://example.com/public/page")
            assert resp.text == "OK"


def test_obey_robots_disallowed_path_raises_error():
    robots_txt = """\
User-agent: *
Disallow: /admin/
"""
    config = ScraperConfig(obey_robots=True)

    def fake_httpx_get(url, *args, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.headers = {}
        if "robots.txt" in str(url):
            resp.text = robots_txt
        else:
            resp.text = "OK"
        return resp

    with patch("httpx.Client.get", side_effect=fake_httpx_get):
        with HttpClient(config) as client:
            with pytest.raises(RobotsDisallowedError) as exc_info:
                client.get("https://example.com/admin/dashboard")
            assert "disallowed" in str(exc_info.value).lower()


def test_robots_fetched_at_most_once_per_host_and_cached_per_client():
    robots_txt = "User-agent: *\nDisallow: /secret/\n"
    config = ScraperConfig(obey_robots=True)
    robots_fetch_count = 0

    def fake_httpx_get(url, *args, **kwargs):
        nonlocal robots_fetch_count
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.headers = {}
        if "robots.txt" in str(url):
            robots_fetch_count += 1
            resp.text = robots_txt
        else:
            resp.text = "OK"
        return resp

    with patch("httpx.Client.get", side_effect=fake_httpx_get):
        with HttpClient(config) as client:
            client.get("https://example.com/page1")
            client.get("https://example.com/page2")
            client.get("https://example.com/page3")
            assert "example.com" in client._robots_cache

    assert robots_fetch_count == 1


def test_crawl_delay_floor_honored():
    robots_txt = """\
User-agent: *
Crawl-delay: 3
"""
    config = ScraperConfig(obey_robots=True, rate_limit=1.0)

    def fake_httpx_get(url, *args, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.headers = {}
        resp.text = robots_txt if "robots.txt" in str(url) else "OK"
        return resp

    with patch("httpx.Client.get", side_effect=fake_httpx_get):
        with HttpClient(config) as client:
            delay = check_robots_sync(client, "https://example.com/page", user_agent="PyScrappyBot")
            assert delay == 3.0


@pytest.mark.anyio
async def test_async_obey_robots_disallowed():
    robots_txt = "User-agent: *\nDisallow: /private/\n"
    config = ScraperConfig(obey_robots=True)

    async def fake_async_get(url, *args, **kwargs):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 200
        resp.headers = {}
        resp.text = robots_txt if "robots.txt" in str(url) else "OK"
        return resp

    with patch("httpx.AsyncClient.get", side_effect=fake_async_get):
        async with AsyncHttpClient(config) as async_client:
            with pytest.raises(RobotsDisallowedError):
                await async_client.get("https://example.com/private/data")
