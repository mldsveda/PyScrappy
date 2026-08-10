"""Tests for TLS-impersonation wiring (ScraperConfig.impersonate).

These don't require curl_cffi to be installed: the not-installed path and the
async guard are tested directly, and the adapter wiring is tested by mocking the
curl_cffi session the StealthClient builds.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from pyscrappy.core._stealth import StealthClient, build_stealth_client, stealth_available
from pyscrappy.core.async_http import AsyncHttpClient
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import PyScrappyError
from pyscrappy.core.http import HttpClient


def test_build_stealth_client_errors_when_curl_cffi_missing():
    if stealth_available():
        pytest.skip("curl_cffi is installed; not-installed path can't be exercised")
    with pytest.raises(PyScrappyError, match="pyscrappy\\[stealth\\]"):
        build_stealth_client("chrome", timeout=10, verify=True)


def test_async_client_rejects_impersonate():
    # Async path doesn't support impersonation yet; constructing must fail loudly
    # rather than silently ignore the setting.
    with pytest.raises(NotImplementedError, match="sync path"):
        AsyncHttpClient(ScraperConfig(impersonate="chrome"))


def test_httpclient_builds_stealth_client_when_impersonate_set():
    # When impersonate is set, HttpClient._build_client routes through the stealth
    # adapter instead of httpx. Patch the adapter so no curl_cffi is needed.
    cfg = ScraperConfig(impersonate="chrome", rate_limit=0)
    client = HttpClient(cfg)
    sentinel = MagicMock(name="stealth_client")
    with patch("pyscrappy.core._stealth.build_stealth_client", return_value=sentinel) as b:
        built = client._build_client()
    assert built is sentinel
    b.assert_called_once()
    # impersonate value is forwarded
    assert b.call_args.args[0] == "chrome" or b.call_args.kwargs.get("impersonate") == "chrome"


def test_httpclient_uses_httpx_when_impersonate_unset():
    client = HttpClient(ScraperConfig(rate_limit=0))
    built = client._build_client()
    assert isinstance(built, httpx.Client)
    built.close()


class _FakeCffiResponse:
    def __init__(self, status_code=200, text="ok", url="http://x"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode()
        self.headers = {}
        self.cookies = {}
        self.url = url


def _stealth_with_fake_session(fake_session):
    """Build a StealthClient with its curl_cffi Session swapped for a fake."""
    sc = StealthClient.__new__(StealthClient)
    sc._session = fake_session
    sc._cffi_errors = (RuntimeError,)  # pretend RuntimeError is curl_cffi's error
    return sc


def test_stealth_response_raise_for_status_maps_to_httpx():
    fake = MagicMock()
    fake.request.return_value = _FakeCffiResponse(status_code=403)
    sc = _stealth_with_fake_session(fake)

    resp = sc.get("http://x", headers={}, follow_redirects=True)
    assert resp.status_code == 403
    with pytest.raises(httpx.HTTPStatusError):
        resp.raise_for_status()


def test_stealth_connection_error_maps_to_httpx_request_error():
    fake = MagicMock()
    fake.request.side_effect = RuntimeError("connection reset")
    sc = _stealth_with_fake_session(fake)
    with pytest.raises(httpx.RequestError, match="connection reset"):
        sc.get("http://x")


def test_stealth_translates_follow_redirects_kwarg():
    fake = MagicMock()
    fake.request.return_value = _FakeCffiResponse()
    sc = _stealth_with_fake_session(fake)
    sc.get("http://x", follow_redirects=True)
    # curl_cffi uses allow_redirects, not follow_redirects
    _, kwargs = fake.request.call_args
    assert kwargs.get("allow_redirects") is True
    assert "follow_redirects" not in kwargs
