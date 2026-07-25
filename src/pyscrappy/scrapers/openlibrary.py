"""Book search scraper (via the Open Library API).

Uses Open Library's public search API (no key required).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_API = "https://openlibrary.org/search.json"


class OpenLibraryScraper(BaseScraper):
    """Search books via Open Library.

    Usage::

        with OpenLibraryScraper() as scraper:
            result = scraper.scrape(query="dune", max_results=10)
    """

    name = "openlibrary"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 20,
    ) -> ScrapeResult:
        """Search for books.

        Args:
            query: Title, author, or free-text search.
            max_results: Maximum books to return.

        Returns:
            ScrapeResult with book data (title, author, year, editions, …).
        """
        url = f"{_API}?q={quote_plus(query)}&limit={max_results}"

        try:
            raw = self.http.get_html(url)
            payload = json.loads(raw)
        except Exception as exc:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
                errors=[ScrapeError(url=url, message=str(exc))],
            )

        books = [
            self._parse(doc)
            for doc in payload.get("docs", [])
            if isinstance(doc, dict)
        ]

        errors: list[ScrapeError] = []
        if not books:
            errors.append(ScrapeError(url=url, message="No books found."))

        return ScrapeResult(
            data=books,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    @staticmethod
    def _parse(doc: dict[str, Any]) -> dict[str, Any]:
        authors = doc.get("author_name") or []
        key = doc.get("key")
        cover = doc.get("cover_i")
        book = {
            "title": doc.get("title"),
            "author": authors[0] if authors else None,
            "authors": authors or None,
            "first_publish_year": doc.get("first_publish_year"),
            "edition_count": doc.get("edition_count"),
            "languages": doc.get("language"),
            "url": f"https://openlibrary.org{key}" if key else None,
            "cover": (
                f"https://covers.openlibrary.org/b/id/{cover}-M.jpg"
                if cover else None
            ),
        }
        return {k: v for k, v in book.items() if v is not None}
