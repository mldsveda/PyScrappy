"""Tests for TLS-impersonation wiring (ScraperConfig.impersonate).

These don't require curl_cffi to be installed: the not-installed path and the
async guard are tested directly, and the adapter wiring is tested by mocking the
curl_cffi session the StealthClient builds.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from pyscrappy.core._stealth import (
    StealthClient,
    build_async_stealth_client,
    build_stealth_client,
    stealth_available,
)
from pyscrappy.core.async_http import AsyncHttpClient
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import PyScrappyError
from pyscrappy.core.http import HttpClient


def test_build_stealth_client_errors_when_curl_cffi_missing():
    if stealth_available():
        pytest.skip("curl_cffi is installed; not-installed path can't be exercised")
    with pytest.raises(PyScrappyError, match="pyscrappy\\[stealth\\]"):
        build_stealth_client("chrome", timeout=10, verify=True)


def test_build_async_stealth_client_errors_when_curl_cffi_missing():
    if stealth_available():
        pytest.skip("curl_cffi is installed; not-installed path can't be exercised")
    with pytest.raises(PyScrappyError, match="pyscrappy\\[stealth\\]"):
        build_async_stealth_client("chrome", timeout=10, verify=True)


def test_async_client_builds_stealth_client_when_impersonate_set():
    # When impersonate is set, AsyncHttpClient._build_client routes through the
    # async stealth adapter instead of httpx.AsyncClient. Patch it so no curl_cffi
    # is needed. (Previously this raised NotImplementedError — now supported.)
    cfg = ScraperConfig(impersonate="chrome", rate_limit=0)
    client = AsyncHttpClient(cfg)
    sentinel = MagicMock(name="async_stealth_client")
    with patch("pyscrappy.core._stealth.build_async_stealth_client", return_value=sentinel) as b:
        built = client._build_client()
    assert built is sentinel
    b.assert_called_once()
    assert b.call_args.args[0] == "chrome" or b.call_args.kwargs.get("impersonate") == "chrome"


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


# -- async adapter: mirror the sync coverage on AsyncStealthClient --


@pytest.fixture
def anyio_backend():
    # Run @pytest.mark.anyio tests on asyncio only (avoids needing trio).
    return "asyncio"


class _FakeAsyncSession:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.request_calls = []

    async def request(self, method, url, **kwargs):
        self.request_calls.append((method, url, kwargs))
        if self._error is not None:
            raise self._error
        return self._response


def _async_stealth_with_fake_session(fake_session):
    from pyscrappy.core._stealth import AsyncStealthClient

    sc = AsyncStealthClient.__new__(AsyncStealthClient)
    sc._session = fake_session
    sc._cffi_errors = (RuntimeError,)
    return sc


@pytest.mark.anyio
async def test_async_stealth_response_maps_to_httpx():
    fake = _FakeAsyncSession(response=_FakeCffiResponse(status_code=403))
    sc = _async_stealth_with_fake_session(fake)
    resp = await sc.get("http://x", follow_redirects=True)
    assert resp.status_code == 403
    with pytest.raises(httpx.HTTPStatusError):
        resp.raise_for_status()
    # follow_redirects is translated to curl_cffi's allow_redirects on the async
    # path too.
    _, _, kwargs = fake.request_calls[0]
    assert kwargs.get("allow_redirects") is True
    assert "follow_redirects" not in kwargs


@pytest.mark.anyio
async def test_async_stealth_connection_error_maps_to_httpx_request_error():
    fake = _FakeAsyncSession(error=RuntimeError("connection reset"))
    sc = _async_stealth_with_fake_session(fake)
    with pytest.raises(httpx.RequestError, match="connection reset"):
        await sc.get("http://x")
