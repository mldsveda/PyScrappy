"""IMDB data via the OMDb API.

IMDB's own pages are protected by AWS WAF (a "Human Verification" challenge that
returns an empty ``202`` to any non-browser client), so they cannot be scraped
directly without CAPTCHA-solving or residential-proxy infrastructure. Instead we
fetch the same data through the free `OMDb API <https://www.omdbapi.com>`_, which
serves IMDB-sourced data as clean JSON.

Set an OMDb API key (free tier available) in the ``OMDB_API_KEY`` environment
variable, or pass ``api_key`` to the constructor.
"""

from __future__ import annotations

import os
import re
from typing import Any

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_OMDB_BASE = "https://www.omdbapi.com/"
_IMDB_ID_RE = re.compile(r"^tt\d+$")


class IMDBScraper(BaseScraper):
    """Fetch movie data from IMDB via the OMDb API.

    Usage::

        # Needs an OMDb API key: export OMDB_API_KEY=... (free at omdbapi.com)
        with IMDBScraper() as scraper:
            # Search by title (returns matches, enriched with details)
            result = scraper.scrape(query="inception")

            # Look up a specific IMDB id
            result = scraper.scrape(query="tt1375666")
    """

    name = "imdb"

    def __init__(
        self,
        config: ScraperConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        super().__init__(config)
        self.api_key = api_key or os.environ.get("OMDB_API_KEY")

    def scrape(  # type: ignore[override]
        self,
        genre: str | None = None,
        query: str | None = None,
        chart: str | None = None,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Fetch movie data from IMDB (via OMDb).

        Args:
            query: A title search term (e.g. ``"inception"``) or an IMDB id
                (e.g. ``"tt1375666"``).
            genre: Not supported — OMDb has no genre-browse endpoint.
            chart: Not supported — OMDb has no chart endpoint.
            max_pages: Pages of search results to fetch (10 results per page).

        Returns:
            ScrapeResult with movie data.
        """
        if genre or chart:
            unsupported = "genre" if genre else "chart"
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(scraper=self.name),
                errors=[
                    ScrapeError(
                        url=_OMDB_BASE,
                        message=(
                            f"{unsupported!r} browsing is not supported. IMDB data "
                            "is served via the OMDb API, which supports title "
                            "search and id lookup only. Use query=<title> or "
                            "query=<imdb id, e.g. tt1375666>."
                        ),
                    )
                ],
            )

        if not query:
            raise ValueError("Provide query=<title or IMDB id>.")

        if not self.api_key:
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(scraper=self.name),
                errors=[
                    ScrapeError(
                        url=_OMDB_BASE,
                        message=(
                            "No OMDb API key. Set the OMDB_API_KEY environment "
                            "variable or pass api_key=... to IMDBScraper. Get a "
                            "free key at https://www.omdbapi.com/apikey.aspx"
                        ),
                    )
                ],
            )

        if _IMDB_ID_RE.match(query.strip()):
            return self._lookup_by_id(query.strip())
        return self._search_by_title(query, max_pages)

    def _get(self, params: dict[str, str]) -> dict[str, Any]:
        """Call OMDb and return the parsed JSON object."""
        params = {**params, "apikey": self.api_key or ""}
        import json

        raw = self.http.get_html(_OMDB_BASE, params=params)
        return json.loads(raw)

    def _lookup_by_id(self, imdb_id: str) -> ScrapeResult:
        errors: list[ScrapeError] = []
        payload = self._get({"i": imdb_id, "plot": "full"})

        if payload.get("Response") == "True":
            data = [self._normalise(payload)]
        else:
            data = []
            errors.append(
                ScrapeError(
                    url=_OMDB_BASE,
                    message=f"OMDb: {payload.get('Error', 'not found')} (id={imdb_id})",
                )
            )

        return ScrapeResult(
            data=data,
            metadata=ScrapeMetadata(source_urls=[_OMDB_BASE], scraper=self.name),
            errors=errors,
        )

    def _search_by_title(self, query: str, max_pages: int) -> ScrapeResult:
        movies: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []

        for page in range(1, max_pages + 1):
            payload = self._get({"s": query, "page": str(page)})

            if payload.get("Response") != "True":
                # OMDb returns "Movie not found!" / "Too many results." as errors.
                if page == 1:
                    errors.append(
                        ScrapeError(
                            url=_OMDB_BASE,
                            message=f"OMDb: {payload.get('Error', 'no results')}",
                        )
                    )
                break

            results = payload.get("Search", [])
            if not results:
                break

            # Enrich each search hit with full details (genre, rating, plot…).
            for hit in results:
                imdb_id = hit.get("imdbID")
                if not imdb_id:
                    movies.append(self._normalise(hit))
                    continue
                details = self._get({"i": imdb_id})
                movies.append(
                    self._normalise(details if details.get("Response") == "True" else hit)
                )

        return ScrapeResult(
            data=movies,
            metadata=ScrapeMetadata(source_urls=[_OMDB_BASE], scraper=self.name),
            errors=errors,
        )

    @staticmethod
    def _normalise(item: dict[str, Any]) -> dict[str, Any]:
        """Map OMDb's PascalCase fields to PyScrappy's lower-case schema.

        OMDb uses ``"N/A"`` for missing values; convert those to ``None``.
        """

        def val(key: str) -> Any:
            v = item.get(key)
            return None if v in (None, "N/A", "") else v

        movie = {
            "title": val("Title"),
            "year": val("Year"),
            "imdb_id": val("imdbID"),
            "type": val("Type"),
            "rated": val("Rated"),
            "released": val("Released"),
            "runtime": val("Runtime"),
            "genre": val("Genre"),
            "director": val("Director"),
            "writer": val("Writer"),
            "actors": val("Actors"),
            "plot": val("Plot"),
            "language": val("Language"),
            "country": val("Country"),
            "rating": val("imdbRating"),
            "votes": val("imdbVotes"),
            "poster": val("Poster"),
        }
        if movie["imdb_id"]:
            movie["url"] = f"https://www.imdb.com/title/{movie['imdb_id']}/"
        # Drop keys that weren't present at all (e.g. search-only results).
        return {k: v for k, v in movie.items() if v is not None}
