"""HTTP client with retry, rate-limiting, and User-Agent rotation."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import NetworkError, RateLimitError

logger = logging.getLogger("pyscrappy.http")


class HttpClient:
    """Sync HTTP client wrapping httpx with automatic retries and rate-limiting.

    Usage::

        config = ScraperConfig(timeout=20, max_retries=2)
        with HttpClient(config) as client:
            html = client.get_html("https://example.com")
    """

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()
        self._client: httpx.Client | None = None
        self._last_request_time: dict[str, float] = {}

    # -- context manager --

    def __enter__(self) -> HttpClient:
        self._client = self._build_client()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # -- public API --

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Perform a GET request with retries and rate-limiting."""
        client = self._ensure_client()
        self._rate_limit(url)

        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                headers = {"User-Agent": self._pick_ua()}
                resp = client.get(url, headers=headers, follow_redirects=True, **kwargs)

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", self.config.retry_delay))
                    if attempt < self.config.max_retries:
                        logger.warning("Rate-limited on %s, retrying in %.1fs", url, retry_after)
                        time.sleep(retry_after)
                        continue
                    raise RateLimitError(f"Rate-limited by {url} after {attempt} attempts")

                resp.raise_for_status()
                return resp

            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code >= 500 and attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** (attempt - 1))
                    logger.warning("Server error %s on %s, retry %d in %.1fs",
                                   exc.response.status_code, url, attempt, delay)
                    time.sleep(delay)
                    continue
                raise NetworkError(
                    f"HTTP {exc.response.status_code} from {url}"
                ) from exc

            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    delay = self.config.retry_delay * (2 ** (attempt - 1))
                    logger.warning("Request error on %s, retry %d in %.1fs", url, attempt, delay)
                    time.sleep(delay)
                    continue

        raise NetworkError(
            f"Failed to fetch {url} after {self.config.max_retries} attempts"
        ) from last_exc

    def get_raw(self, url: str, **kwargs: Any) -> httpx.Response:
        """Like :meth:`get` but does NOT raise on non-2xx status codes.

        Useful when the caller needs to inspect the status code itself
        (e.g. to detect auth failures and retry with new credentials).
        """
        client = self._ensure_client()
        self._rate_limit(url)
        headers = {"User-Agent": self._pick_ua()}
        return client.get(url, headers=headers, follow_redirects=True, **kwargs)

    def get_html(self, url: str, **kwargs: Any) -> str:
        """Fetch a URL and return the response body as text."""
        return self.get(url, **kwargs).text

    # -- internals --

    def _build_client(self) -> httpx.Client:
        transport_kwargs: dict[str, Any] = {}
        if self.config.proxy:
            transport_kwargs["proxy"] = self.config.proxy
        return httpx.Client(
            timeout=self.config.timeout,
            verify=self.config.verify_ssl,
            **transport_kwargs,
        )

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    def _pick_ua(self) -> str:
        return random.choice(self.config.user_agents)

    def _rate_limit(self, url: str) -> None:
        from urllib.parse import urlparse

        domain = urlparse(url).netloc
        now = time.monotonic()
        last = self._last_request_time.get(domain, 0.0)
        wait = self.config.rate_limit - (now - last)
        if wait > 0:
            logger.debug("Rate-limiting %s: sleeping %.2fs", domain, wait)
            time.sleep(wait)
        self._last_request_time[domain] = time.monotonic()
