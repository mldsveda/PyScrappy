"""Tests for pyscrappy.scrapers.imdb (OMDb-backed)."""

import json
import asyncio

from unittest.mock import MagicMock, AsyncMock


import pytest

from pyscrappy.core.models import ScrapeResult
from pyscrappy.scrapers.imdb import IMDBScraper

# --- Sample OMDb payloads ---------------------------------------------------

DETAILS_JSON = json.dumps(
    {
        "Title": "Inception",
        "Year": "2010",
        "Rated": "PG-13",
        "Runtime": "148 min",
        "Genre": "Action, Adventure, Sci-Fi",
        "Director": "Christopher Nolan",
        "Actors": "Leonardo DiCaprio, Joseph Gordon-Levitt",
        "Plot": "A thief who steals corporate secrets...",
        "imdbRating": "8.8",
        "imdbVotes": "2,500,000",
        "imdbID": "tt1375666",
        "Type": "movie",
        "Poster": "https://example.com/poster.jpg",
        "Response": "True",
    }
)

SEARCH_JSON = json.dumps(
    {
        "Search": [
            {
                "Title": "Inception",
                "Year": "2010",
                "imdbID": "tt1375666",
                "Type": "movie",
                "Poster": "https://example.com/p.jpg",
            },
        ],
        "totalResults": "41",
        "Response": "True",
    }
)

NOT_FOUND_JSON = json.dumps({"Response": "False", "Error": "Movie not found!"})


def _scraper_with(responses):
    """Build an IMDBScraper whose HTTP layer returns queued JSON strings."""
    scraper = IMDBScraper(api_key="testkey")
    mock_http = MagicMock()
    mock_http.get_html.side_effect = responses
    scraper._http = mock_http  # bypass real network
    return scraper

def _scraper_with_async(responses):
    """Build an IMDBScraper whose async HTTP layer returns queued JSON strings."""
    scraper = IMDBScraper(api_key="testkey")
    mock_async_http = MagicMock()
    mock_async_http.get_html = AsyncMock(side_effect=responses)
    scraper._async_http = mock_async_http
    return scraper


class TestIMDBScraperInit:
    def test_name(self):
        assert IMDBScraper(api_key="k").name == "imdb"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OMDB_API_KEY", "from-env")
        assert IMDBScraper().api_key == "from-env"

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OMDB_API_KEY", "from-env")
        assert IMDBScraper(api_key="explicit").api_key == "explicit"


class TestIMDBScraperValidation:
    def test_no_query_raises(self):
        with pytest.raises(ValueError, match="Provide query"):
            IMDBScraper(api_key="k").scrape()

    def test_genre_returns_unsupported_error(self):
        result = IMDBScraper(api_key="k").scrape(genre="sci-fi")
        assert isinstance(result, ScrapeResult)
        assert result.data == []
        assert result.errors
        assert "not supported" in result.errors[0].message

    def test_chart_returns_unsupported_error(self):
        result = IMDBScraper(api_key="k").scrape(chart="top250")
        assert result.data == []
        assert "not supported" in result.errors[0].message

    def test_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("OMDB_API_KEY", raising=False)
        result = IMDBScraper(api_key=None).scrape(query="inception")
        assert result.data == []
        assert "OMDb API key" in result.errors[0].message


class TestIMDBLookupById:
    def test_lookup_by_id(self):
        scraper = _scraper_with([DETAILS_JSON])
        result = scraper.scrape(query="tt1375666")
        assert len(result.data) == 1
        movie = result.data[0]
        assert movie["title"] == "Inception"
        assert movie["rating"] == "8.8"
        assert movie["imdb_id"] == "tt1375666"
        assert movie["url"] == "https://www.imdb.com/title/tt1375666/"

    def test_lookup_by_id_not_found(self):
        scraper = _scraper_with([NOT_FOUND_JSON])
        result = scraper.scrape(query="tt0000000")
        assert result.data == []
        assert "not found" in result.errors[0].message.lower()


class TestIMDBSearchByTitle:
    def test_search_enriches_with_details(self):
        # First call: search list. Second call: details for the one hit.
        scraper = _scraper_with([SEARCH_JSON, DETAILS_JSON])
        result = scraper.scrape(query="inception", max_pages=1)
        assert len(result.data) == 1
        assert result.data[0]["genre"] == "Action, Adventure, Sci-Fi"
        assert result.data[0]["director"] == "Christopher Nolan"

    def test_search_no_results(self):
        scraper = _scraper_with([NOT_FOUND_JSON])
        result = scraper.scrape(query="zzzznotarealmovie")
        assert result.data == []
        assert result.errors

    def test_search_without_enrich_skips_details(self):
        # Queue only the search page — a stray detail-lookup call would error out.
        scraper = _scraper_with([SEARCH_JSON])
        result = scraper.scrape(query="inception", max_pages=1, enrich=False)

        assert scraper._http.get_html.call_count == 1
        assert len(result.data) == 1
        assert result.errors == []

class TestIMDBSearchByTitleAsync:
    def test_search_async_enriches_with_details(self):
        # First call: search list. Second call: details for the one hit.
        scraper = _scraper_with_async([SEARCH_JSON, DETAILS_JSON])
        result = asyncio.run(
            scraper.scrape_async(query="inception", max_pages=1)
        )
        assert len(result.data) == 1
        assert result.data[0]["genre"] == "Action, Adventure, Sci-Fi"
        assert result.data[0]["director"] == "Christopher Nolan"

    def test_search_async_no_results(self):
        scraper = _scraper_with_async([NOT_FOUND_JSON])
        result = asyncio.run(
            scraper.scrape_async(query="zzzznotarealmovie")
        )
        assert result.data == []
        assert result.errors

    def test_search_async_without_enrich_skips_details(self):
        scraper = _scraper_with_async([SEARCH_JSON])
        result = asyncio.run(
            scraper.scrape_async(query="inception", max_pages=1, enrich=False)
        )

        assert scraper._async_http.get_html.call_count == 1
        assert len(result.data) == 1
        assert result.errors == []


class TestNormalise:
    def test_na_becomes_absent(self):
        payload = json.dumps(
            {
                "Title": "X",
                "Year": "2020",
                "imdbID": "tt1",
                "Rated": "N/A",
                "Director": "N/A",
                "Response": "True",
            }
        )
        scraper = _scraper_with([payload])
        movie = scraper.scrape(query="tt1").data[0]
        assert movie["title"] == "X"
        assert "rated" not in movie  # "N/A" dropped
        assert "director" not in movie
