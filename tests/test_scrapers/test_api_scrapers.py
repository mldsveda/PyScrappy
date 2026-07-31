"""Tests for the JSON-API-based scrapers: GitHub, HackerNews, OpenLibrary, Weather."""

import json
from unittest.mock import MagicMock

from pyscrappy.scrapers.github import GitHubScraper
from pyscrappy.scrapers.hackernews import HackerNewsScraper
from pyscrappy.scrapers.openlibrary import OpenLibraryScraper
from pyscrappy.scrapers.weather import WeatherScraper


def _with(scraper, *responses):
    scraper._http = MagicMock()
    scraper._http.get_html.side_effect = responses
    return scraper


class TestGitHub:
    def test_parse(self):
        payload = json.dumps(
            {
                "items": [
                    {
                        "name": "pyscrappy",
                        "full_name": "mldsveda/pyscrappy",
                        "owner": {"login": "mldsveda"},
                        "description": "scraping toolkit",
                        "html_url": "https://github.com/mldsveda/pyscrappy",
                        "stargazers_count": 90,
                        "forks_count": 31,
                        "language": "Python",
                        "open_issues_count": 2,
                        "updated_at": "2026-01-01",
                    }
                ]
            }
        )
        s = _with(GitHubScraper(token="t"), payload)
        r = s.scrape(query="scraping")
        assert len(r.data) == 1
        repo = r.data[0]
        assert repo["full_name"] == "mldsveda/pyscrappy"
        assert repo["owner"] == "mldsveda"
        assert repo["stars"] == 90
        assert repo["language"] == "Python"

    def test_empty_reports_message(self):
        s = _with(GitHubScraper(), json.dumps({"items": [], "message": "rate limited"}))
        r = s.scrape(query="x")
        assert r.data == []
        assert "rate limited" in r.errors[0].message


class TestHackerNews:
    def test_parse(self):
        payload = json.dumps(
            {
                "hits": [
                    {
                        "title": "Show HN: PyScrappy",
                        "url": "https://example.com",
                        "points": 42,
                        "author": "veda",
                        "num_comments": 7,
                        "created_at": "2026-01-01",
                        "objectID": "12345",
                    }
                ]
            }
        )
        s = _with(HackerNewsScraper(), payload)
        r = s.scrape(query="pyscrappy")
        assert len(r.data) == 1
        story = r.data[0]
        assert story["title"] == "Show HN: PyScrappy"
        assert story["points"] == 42
        assert story["hn_url"] == "https://news.ycombinator.com/item?id=12345"

    def test_by_date_uses_date_endpoint(self):
        s = _with(HackerNewsScraper(), json.dumps({"hits": []}))
        s.scrape(query="x", by="date")
        url = s._http.get_html.call_args[0][0]
        assert "search_by_date" in url


class TestOpenLibrary:
    def test_parse(self):
        payload = json.dumps(
            {
                "docs": [
                    {
                        "title": "Dune",
                        "author_name": ["Frank Herbert"],
                        "first_publish_year": 1965,
                        "edition_count": 100,
                        "language": ["eng"],
                        "key": "/works/OL893415W",
                        "cover_i": 111,
                    }
                ]
            }
        )
        s = _with(OpenLibraryScraper(), payload)
        r = s.scrape(query="dune")
        assert len(r.data) == 1
        book = r.data[0]
        assert book["title"] == "Dune"
        assert book["author"] == "Frank Herbert"
        assert book["first_publish_year"] == 1965
        assert book["url"] == "https://openlibrary.org/works/OL893415W"

    def test_empty(self):
        s = _with(OpenLibraryScraper(), json.dumps({"docs": []}))
        r = s.scrape(query="zzz")
        assert r.data == []
        assert r.errors


class TestWeather:
    def test_geocode_then_forecast(self):
        geo = json.dumps(
            {
                "results": [
                    {
                        "name": "London",
                        "country": "United Kingdom",
                        "latitude": 51.5,
                        "longitude": -0.12,
                    }
                ]
            }
        )
        forecast = json.dumps(
            {
                "current": {
                    "time": "2026-01-01T12:00",
                    "temperature_2m": 15.0,
                    "relative_humidity_2m": 60,
                    "wind_speed_10m": 10.0,
                    "weather_code": 3,
                },
                "current_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
            }
        )
        s = _with(WeatherScraper(), geo, forecast)
        r = s.scrape(location="London")
        assert len(r.data) == 1
        w = r.data[0]
        assert w["location"] == "London"
        assert w["temperature"] == 15.0
        assert w["condition"] == "Overcast"  # WMO code 3

    def test_location_not_found(self):
        s = _with(WeatherScraper(), json.dumps({"results": []}))
        r = s.scrape(location="Xyzzy")
        assert r.data == []
        assert "not found" in r.errors[0].message
