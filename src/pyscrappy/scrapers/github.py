"""GitHub repository search scraper (via the GitHub REST API).

Uses GitHub's public search API. Unauthenticated requests are rate-limited to
10 search requests/minute, which is fine for interactive use. Pass a token to
raise the limit.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_API = "https://api.github.com/search/repositories"


class GitHubScraper(BaseScraper):
    """Search GitHub repositories.

    Usage::

        with GitHubScraper() as scraper:
            result = scraper.scrape(query="web scraping", max_results=10)

        # With a token to raise the rate limit:
        with GitHubScraper(token="ghp_...") as scraper:
            result = scraper.scrape(query="mcp server", sort="stars")
    """

    name = "github"

    def __init__(
        self,
        config: ScraperConfig | None = None,
        token: str | None = None,
    ) -> None:
        super().__init__(config)
        self.token = token

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 20,
        sort: str = "best-match",
    ) -> ScrapeResult:
        """Search GitHub repositories.

        Args:
            query: Search query, e.g. ``"web scraping language:python"``.
            max_results: Maximum repositories to return (max 100 per request).
            sort: ``"best-match"`` (default), ``"stars"``, ``"forks"``, or ``"updated"``.

        Returns:
            ScrapeResult with repo data (name, owner, stars, description, url, …).
        """
        per_page = min(max_results, 100)
        url = f"{_API}?q={quote_plus(query)}&per_page={per_page}"
        if sort != "best-match":
            url += f"&sort={sort}"

        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            raw = self.http.get_html(url, headers=headers)
            payload = json.loads(raw)
        except Exception as exc:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
                errors=[ScrapeError(url=url, message=str(exc))],
            )

        return self._build_result(payload, url)

    async def scrape_async(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 20,
        sort: str = "best-match",
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` (same args/returns)."""
        per_page = min(max_results, 100)
        url = f"{_API}?q={quote_plus(query)}&per_page={per_page}"
        if sort != "best-match":
            url += f"&sort={sort}"

        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            raw = await self.async_http.get_html(url, headers=headers)
            payload = json.loads(raw)
        except Exception as exc:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
                errors=[ScrapeError(url=url, message=str(exc))],
            )

        return self._build_result(payload, url)

    def _build_result(self, payload: dict[str, Any], url: str) -> ScrapeResult:
        """Shared payload handling for the sync and async scrape paths."""
        items = payload.get("items", [])
        repos = [self._parse(item) for item in items if isinstance(item, dict)]

        errors: list[ScrapeError] = []
        if not repos:
            msg = payload.get("message", "No repositories found.")
            errors.append(ScrapeError(url=url, message=str(msg)))

        return ScrapeResult(
            data=repos,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    @staticmethod
    def _parse(item: dict[str, Any]) -> dict[str, Any]:
        owner = item.get("owner") or {}
        repo = {
            "name": item.get("name"),
            "full_name": item.get("full_name"),
            "owner": owner.get("login") if isinstance(owner, dict) else None,
            "description": item.get("description"),
            "url": item.get("html_url"),
            "stars": item.get("stargazers_count"),
            "forks": item.get("forks_count"),
            "language": item.get("language"),
            "open_issues": item.get("open_issues_count"),
            "updated_at": item.get("updated_at"),
        }
        return {k: v for k, v in repo.items() if v is not None}
