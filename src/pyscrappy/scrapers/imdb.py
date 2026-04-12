"""IMDB scraper — search movies by genre, title, or get top charts."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_IMDB_BASE = "https://www.imdb.com"

_VALID_GENRES = {
    "action", "adventure", "animation", "biography", "comedy", "crime",
    "documentary", "drama", "family", "fantasy", "film-noir", "history",
    "horror", "music", "musical", "mystery", "romance", "sci-fi",
    "sport", "thriller", "war", "western",
}


class IMDBScraper(BaseScraper):
    """Scrape movie data from IMDB.

    Usage::

        with IMDBScraper() as scraper:
            # Search by genre
            result = scraper.scrape(genre="sci-fi", max_pages=3)

            # Search by title
            result = scraper.scrape(query="inception")

            # Top 250
            result = scraper.scrape(chart="top250")
    """

    name = "imdb"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        genre: str | None = None,
        query: str | None = None,
        chart: str | None = None,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Scrape movies from IMDB.

        Args:
            genre: A genre name (e.g. ``"sci-fi"``, ``"comedy"``).
            query: Free-text title search.
            chart: Chart name — ``"top250"`` or ``"popular"``.
            max_pages: Pages to scrape (genre/query search only).

        Returns:
            ScrapeResult with movie data.
        """
        if chart:
            return self._scrape_chart(chart)
        if genre:
            return self._scrape_search(genre=genre, max_pages=max_pages)
        if query:
            return self._scrape_search(query=query, max_pages=max_pages)
        raise ValueError("Provide at least one of: genre, query, or chart")

    def _scrape_chart(self, chart: str) -> ScrapeResult:
        if chart == "top250":
            url = f"{_IMDB_BASE}/chart/top/"
        elif chart == "popular":
            url = f"{_IMDB_BASE}/chart/moviemeter/"
        else:
            raise ValueError(f"Unknown chart: {chart!r}. Use 'top250' or 'popular'.")

        soup = self.fetch_and_parse(url)
        movies: list[dict[str, Any]] = []

        for item in soup.select("li.ipc-metadata-list-summary-item"):
            movie = self._parse_chart_item(item)
            if movie:
                movies.append(movie)

        return ScrapeResult(
            data=movies,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _scrape_search(
        self,
        genre: str | None = None,
        query: str | None = None,
        max_pages: int = 1,
    ) -> ScrapeResult:
        movies: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []

        params: dict[str, str] = {}
        if genre:
            genre = genre.lower()
            if genre not in _VALID_GENRES:
                raise ValueError(
                    f"Unknown genre: {genre!r}. Valid: {sorted(_VALID_GENRES)}"
                )
            params["genres"] = genre
            params["title_type"] = "feature"
        if query:
            params["title"] = query

        base_url = f"{_IMDB_BASE}/search/title/?" + urlencode(params)

        for page in range(1, max_pages + 1):
            url = base_url if page == 1 else f"{base_url}&start={1 + (page - 1) * 50}"
            visited.append(url)

            try:
                soup = self.fetch_and_parse(url)
            except Exception as exc:
                errors.append(ScrapeError(url=url, message=str(exc)))
                break

            items = soup.select(".lister-item-content, .ipc-metadata-list-summary-item")
            if not items:
                break

            for item in items:
                movie = self._parse_search_item(item)
                if movie:
                    movies.append(movie)

        return ScrapeResult(
            data=movies,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=errors,
        )

    def _parse_chart_item(self, item: Tag) -> dict[str, Any] | None:
        movie: dict[str, Any] = {}

        # Title + link
        title_el = item.select_one("h3.ipc-title__text")
        if title_el:
            movie["title"] = title_el.get_text(strip=True)
        link = item.select_one("a.ipc-title-link-wrapper")
        if link:
            movie["url"] = _IMDB_BASE + str(link.get("href", "")).split("?")[0]

        # Metadata spans (year, runtime, rating)
        meta_items = item.select("span.cli-title-metadata-item")
        if len(meta_items) >= 1:
            movie["year"] = meta_items[0].get_text(strip=True)
        if len(meta_items) >= 2:
            movie["runtime"] = meta_items[1].get_text(strip=True)
        if len(meta_items) >= 3:
            movie["certificate"] = meta_items[2].get_text(strip=True)

        # Rating
        rating_el = item.select_one("span.ipc-rating-star--rating")
        if rating_el:
            movie["rating"] = rating_el.get_text(strip=True)

        # Vote count
        vote_el = item.select_one("span.ipc-rating-star--voteCount")
        if vote_el:
            movie["votes"] = vote_el.get_text(strip=True).strip("()")

        return movie if movie.get("title") else None

    def _parse_search_item(self, item: Tag) -> dict[str, Any] | None:
        movie: dict[str, Any] = {}

        # Try modern IMDB layout first
        title_el = item.select_one("h3.ipc-title__text, h3.lister-item-header a")
        if title_el:
            movie["title"] = title_el.get_text(strip=True)

        # Link
        link = item.select_one("a.ipc-title-link-wrapper, h3.lister-item-header a")
        if link:
            href = str(link.get("href", ""))
            movie["url"] = _IMDB_BASE + href.split("?")[0] if href.startswith("/") else href

        # Year
        year_el = item.select_one(
            "span.lister-item-year, span.cli-title-metadata-item"
        )
        if year_el:
            movie["year"] = year_el.get_text(strip=True).strip("()")

        # Rating
        rating_el = item.select_one(
            "div.ratings-imdb-rating strong, span.ipc-rating-star--rating"
        )
        if rating_el:
            movie["rating"] = rating_el.get_text(strip=True)

        # Description
        desc_els = item.select("p.text-muted")
        for el in desc_els:
            text = el.get_text(strip=True)
            if len(text) > 50:
                movie["description"] = text
                break

        # Genre
        genre_el = item.select_one("span.genre")
        if genre_el:
            movie["genre"] = genre_el.get_text(strip=True)

        # Runtime
        runtime_el = item.select_one("span.runtime")
        if runtime_el:
            movie["runtime"] = runtime_el.get_text(strip=True)

        return movie if movie.get("title") else None
