"""Hacker News search scraper (via the Algolia HN Search API).

Uses the public Algolia-backed HN Search API (no key required).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_API = "https://hn.algolia.com/api/v1/search"


class HackerNewsScraper(BaseScraper):
    """Search Hacker News stories.

    Usage::

        with HackerNewsScraper() as scraper:
            result = scraper.scrape(query="large language models", max_results=10)

        # Sort by most recent instead of relevance:
        result = scraper.scrape(query="rust", by="date")
    """

    name = "hackernews"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 20,
        by: str = "relevance",
        tags: str = "story",
    ) -> ScrapeResult:
        """Search Hacker News.

        Args:
            query: Search query.
            max_results: Maximum results to return (max 1000).
            by: ``"relevance"`` (default) or ``"date"`` (most recent first).
            tags: HN tag filter, e.g. ``"story"``, ``"comment"``, ``"show_hn"``.

        Returns:
            ScrapeResult with story data (title, url, points, author, comments, …).
        """
        endpoint = "search_by_date" if by == "date" else "search"
        base = _API.replace("/search", f"/{endpoint}")
        hits = min(max_results, 1000)
        url = f"{base}?query={quote_plus(query)}&tags={tags}&hitsPerPage={hits}"

        try:
            raw = self.http.get_html(url)
            payload = json.loads(raw)
        except Exception as exc:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
                errors=[ScrapeError(url=url, message=str(exc))],
            )

        stories = [
            self._parse(hit)
            for hit in payload.get("hits", [])
            if isinstance(hit, dict)
        ]

        errors: list[ScrapeError] = []
        if not stories:
            errors.append(ScrapeError(url=url, message="No stories found."))

        return ScrapeResult(
            data=stories,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    @staticmethod
    def _parse(hit: dict[str, Any]) -> dict[str, Any]:
        object_id = hit.get("objectID")
        story = {
            "title": hit.get("title"),
            "url": hit.get("url"),
            "points": hit.get("points"),
            "author": hit.get("author"),
            "num_comments": hit.get("num_comments"),
            "created_at": hit.get("created_at"),
            "hn_url": (
                f"https://news.ycombinator.com/item?id={object_id}"
                if object_id else None
            ),
        }
        return {k: v for k, v in story.items() if v is not None}
