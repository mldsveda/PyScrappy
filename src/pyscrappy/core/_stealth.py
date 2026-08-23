"""TLS-fingerprint impersonation for the sync HTTP client, via ``curl_cffi``.

A plain HTTP client has a recognizable TLS/JA3 fingerprint that many anti-bot
systems block outright, before any content is served. ``curl_cffi`` speaks TLS
the way a real browser does, so ``ScraperConfig(impersonate="chrome")`` gets past
that class of block without a headless browser.

This is an *adapter*: it wraps ``curl_cffi``'s session so it looks enough like an
``httpx.Client`` (same ``.get``/``.post`` surface, and it raises the same
``httpx`` exception types) that the retry/rate-limit/cache/robots machinery in
``HttpClient`` works unchanged. ``curl_cffi`` is optional; import errors surface a
clear install hint.
"""

from __future__ import annotations

from typing import Any

import httpx

_INSTALL_HINT = (
    "TLS impersonation needs the optional 'curl_cffi' dependency. "
    "Install it with: pip install 'pyscrappy[stealth]'"
)


def stealth_available() -> bool:
    try:
        import curl_cffi  # noqa: F401

        return True
    except ImportError:
        return False


class _StealthResponse:
    """Wrap a curl_cffi response with the httpx surface HttpClient relies on
    (``.text``, ``.status_code``, ``.headers``, ``.cookies``, ``raise_for_status``)."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    @property
    def text(self) -> str:
        return self._raw.text

    @property
    def content(self) -> bytes:
        return self._raw.content

    @property
    def status_code(self) -> int:
        return self._raw.status_code

    @property
    def headers(self) -> Any:
        return self._raw.headers

    @property
    def cookies(self) -> Any:
        return self._raw.cookies

    def raise_for_status(self) -> None:
        # Normalize to httpx.HTTPStatusError so HttpClient's except clause catches it.
        if self.status_code >= 400:
            request = httpx.Request("GET", str(getattr(self._raw, "url", "")))
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=request, response=response
            )


class StealthClient:
    """A thin ``curl_cffi`` session presenting an ``httpx.Client``-like interface.

    Only the methods ``HttpClient`` calls are implemented (``get``, ``post``,
    ``cookies``, ``close``). Connection failures are re-raised as
    ``httpx.RequestError`` so the existing retry loop treats them identically.
    """

    def __init__(
        self,
        impersonate: str,
        timeout: float,
        verify: bool,
        proxy: str | None = None,
    ) -> None:
        from curl_cffi import requests as cffi

        self._cffi_errors = self._import_errors()
        session_kwargs: dict[str, Any] = {
            "impersonate": impersonate,
            "timeout": timeout,
            "verify": verify,
        }
        if proxy:
            session_kwargs["proxies"] = {"http": proxy, "https": proxy}
        self._session = cffi.Session(**session_kwargs)

    @staticmethod
    def _import_errors() -> tuple[type[Exception], ...]:
        try:
            from curl_cffi.requests.errors import RequestsError

            return (RequestsError,)
        except ImportError:  # older/newer curl_cffi layout
            try:
                from curl_cffi import CurlError

                return (CurlError,)
            except ImportError:
                return ()

    @property
    def cookies(self) -> Any:
        return self._session.cookies

    def _request(self, method: str, url: str, **kwargs: Any) -> _StealthResponse:
        # httpx uses follow_redirects=; curl_cffi uses allow_redirects=.
        if "follow_redirects" in kwargs:
            kwargs["allow_redirects"] = kwargs.pop("follow_redirects")
        try:
            raw = self._session.request(method, url, **kwargs)
        except self._cffi_errors as exc:  # network/transport failure
            request = httpx.Request(method, url)
            raise httpx.RequestError(str(exc), request=request) from exc
        return _StealthResponse(raw)

    def get(self, url: str, **kwargs: Any) -> _StealthResponse:
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> _StealthResponse:
        return self._request("POST", url, **kwargs)

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:  # noqa: BLE001 - closing should never raise upward
            pass


def build_stealth_client(
    impersonate: str, timeout: float, verify: bool, proxy: str | None = None
) -> StealthClient:
    """Build a StealthClient, raising a clear error if curl_cffi isn't installed."""
    if not stealth_available():
        from pyscrappy.core.exceptions import PyScrappyError

        raise PyScrappyError(_INSTALL_HINT)
    return StealthClient(impersonate, timeout, verify, proxy)


class AsyncStealthClient:
    """Async counterpart of :class:`StealthClient`, presenting the subset of the
    ``httpx.AsyncClient`` surface that ``AsyncHttpClient`` calls (``get``,
    ``post``, ``cookies``, ``aclose``) over ``curl_cffi``'s ``AsyncSession``.

    Like the sync adapter, transport failures are re-raised as
    ``httpx.RequestError`` and non-2xx normalize to ``httpx.HTTPStatusError``, so
    the async retry/rate-limit/cache/robots machinery works unchanged.
    """

    def __init__(
        self,
        impersonate: str,
        timeout: float,
        verify: bool,
        proxy: str | None = None,
    ) -> None:
        from curl_cffi.requests import AsyncSession

        self._cffi_errors = StealthClient._import_errors()
        session_kwargs: dict[str, Any] = {
            "impersonate": impersonate,
            "timeout": timeout,
            "verify": verify,
        }
        if proxy:
            session_kwargs["proxies"] = {"http": proxy, "https": proxy}
        self._session = AsyncSession(**session_kwargs)

    @property
    def cookies(self) -> Any:
        return self._session.cookies

    async def _request(self, method: str, url: str, **kwargs: Any) -> _StealthResponse:
        if "follow_redirects" in kwargs:
            kwargs["allow_redirects"] = kwargs.pop("follow_redirects")
        try:
            raw = await self._session.request(method, url, **kwargs)
        except self._cffi_errors as exc:  # network/transport failure
            request = httpx.Request(method, url)
            raise httpx.RequestError(str(exc), request=request) from exc
        return _StealthResponse(raw)

    async def get(self, url: str, **kwargs: Any) -> _StealthResponse:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> _StealthResponse:
        return await self._request("POST", url, **kwargs)

    async def aclose(self) -> None:
        try:
            await self._session.close()
        except Exception:  # noqa: BLE001 - closing should never raise upward
            pass


def build_async_stealth_client(
    impersonate: str, timeout: float, verify: bool, proxy: str | None = None
) -> AsyncStealthClient:
    """Build an AsyncStealthClient, raising a clear error if curl_cffi is absent."""
    if not stealth_available():
        from pyscrappy.core.exceptions import PyScrappyError

        raise PyScrappyError(_INSTALL_HINT)
    return AsyncStealthClient(impersonate, timeout, verify, proxy)
