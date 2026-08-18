"""Google web search via the SerpBase Search API.

Google's own search pages are served to interactive browsers only: plain HTTP
clients get a consent interstitial or a CAPTCHA before parsing ever sees a
result, and the markup changes often enough that selector maintenance is a
constant cost. The SerpBase Search API (https://serpbase.dev) returns the same
organic results as clean JSON, so this scraper needs no browser, no CAPTCHA
handling, and no selector upkeep.

Set a SerpBase API key in the ``SERPBASE_API_KEY`` environment variable, or
pass ``api_key`` to the constructor. New accounts start with 100 free searches
(no credit card required); afterwards it is pay-as-you-go ($0.30 per 1k
queries).
"""

from __future__ import annotations

import json
import os
from typing import Any

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_SERP_BASE_URL = "https://api.serpbase.dev/google/search"
_DEFAULT_MAX_RESULTS = 10


class GoogleSearchScraper(BaseScraper):
    """Fetch Google web search results as JSON via the SerpBase API.

    Usage::

        # Needs an API key: export SERPBASE_API_KEY=... (free trial at serpbase.dev)
        with GoogleSearchScraper() as scraper:
            result = scraper.scrape(query="pyscrappy web scraping")

            # Locale-aware searches mirror Google's hl/gl parameters
            result = scraper.scrape(
                query="best pizza",
                language="it",   # hl=it
                country="it",    # gl=it
            )

    Each record in ``result.data`` has ``title``, ``link``, ``snippet`` and
    ``position`` keys, in Google's ranking order.
    """

    name = "google_search"

    def __init__(
        self,
        config: ScraperConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__(config)
        self.api_key = api_key or os.environ.get("SERPBASE_API_KEY")

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        language: str | None = None,
        country: str | None = None,
    ) -> ScrapeResult:
        """Search Google and return organic results via the SerpBase API.

        Args:
            query: The search terms, exactly as you would type them into Google.
            max_results: Maximum number of organic results to return (the API
                response is truncated to this many records).
            language: Optional Google interface language, e.g. ``"de"``.
            country: Optional Google results region, e.g. ``"de"``.

        Returns:
            ScrapeResult with one record per organic result (``title``,
            ``link``, ``snippet``, ``position``).
        """
        if not query:
            raise ValueError("Provide query=<search terms>.")

        if not self.api_key:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(scraper=self.name),
                errors=[
                    ScrapeError(
                        url=_SERP_BASE_URL,
                        message=(
                            "No SerpBase API key. Set the SERPBASE_API_KEY "
                            "environment variable or pass api_key=... to "
                            "GoogleSearchScraper. Get a free key (100 free "
                            "searches, no credit card) at https://serpbase.dev"
                        ),
                    )
                ],
            )

        payload: dict[str, Any] = {"q": query}
        if language:
            payload["hl"] = language
        if country:
            payload["gl"] = country

        raw = self.http.post_json(
            _SERP_BASE_URL,
            json=payload,
            headers={"X-API-Key": self.api_key},
        )
        return self._build_result(json.loads(raw), max_results=max_results)

    async def scrape_async(  # type: ignore[override]
        self,
        query: str,
        max_results: int = _DEFAULT_MAX_RESULTS,
        language: str | None = None,
        country: str | None = None,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` (same args/returns)."""
        if not query:
            raise ValueError("Provide query=<search terms>.")

        if not self.api_key:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(scraper=self.name),
                errors=[
                    ScrapeError(
                        url=_SERP_BASE_URL,
                        message=(
                            "No SerpBase API key. Set the SERPBASE_API_KEY "
                            "environment variable or pass api_key=... to "
                            "GoogleSearchScraper. Get a free key (100 free "
                            "searches, no credit card) at https://serpbase.dev"
                        ),
                    )
                ],
            )

        payload: dict[str, Any] = {"q": query}
        if language:
            payload["hl"] = language
        if country:
            payload["gl"] = country

        raw = await self.async_http.post_json(
            _SERP_BASE_URL,
            json=payload,
            headers={"X-API-Key": self.api_key},
        )
        return self._build_result(json.loads(raw), max_results=max_results)

    def _build_result(
        self, payload: dict[str, Any], max_results: int
    ) -> ScrapeResult:
        """Map the SerpBase envelope to a ScrapeResult.

        The API always answers 200 and reports failures through the business
        envelope instead: ``status`` is 0 on success and non-zero on failure,
        so a failed request surfaces as a clear per-call error rather than as
        an empty result set that looks like "no results found".
        """
        if payload.get("status") != 0:
            detail = payload.get("error") or payload.get("message") or "request failed"
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(scraper=self.name),
                errors=[
                    ScrapeError(
                        url=_SERP_BASE_URL,
                        message=f"SerpBase: {detail} (status={payload.get('status')})",
                    )
                ],
            )

        data: list[dict[str, Any]] = []
        for item in payload.get("organic") or []:
            data.append(
                {
                    "title": item.get("title", ""),
                    "link": item.get("link") or item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                    "position": item.get("position", len(data) + 1),
                }
            )
        if max_results > 0:
            data = data[:max_results]

        return ScrapeResult(
            data=data,
            metadata=ScrapeMetadata(source_urls=[_SERP_BASE_URL], scraper=self.name),
            errors=[],
        )
