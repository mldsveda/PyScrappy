"""Tests for the SerpBase-backed GoogleSearchScraper."""

import json
from unittest.mock import MagicMock

from pyscrappy.scrapers.google_search import GoogleSearchScraper


def _with(scraper, *responses):
    scraper._http = MagicMock()
    scraper._http.post_json.side_effect = responses
    return scraper


class TestGoogleSearch:
    def test_parse(self):
        payload = json.dumps(
            {
                "status": 0,
                "request_id": "req_1",
                "organic": [
                    {
                        "title": "PyScrappy",
                        "link": "https://github.com/mldsveda/PyScrappy",
                        "snippet": "A robust Python web scraping toolkit.",
                        "position": 1,
                    },
                    {
                        "title": "Scraping API",
                        "link": "https://example.com",
                        "snippet": "JSON search results.",
                        "position": 2,
                    },
                ],
            }
        )
        s = _with(GoogleSearchScraper(api_key="k"), payload)
        r = s.scrape(query="pyscrappy")
        assert len(r.data) == 2
        first = r.data[0]
        assert first["title"] == "PyScrappy"
        assert first["link"] == "https://github.com/mldsveda/PyScrappy"
        assert first["snippet"] == "A robust Python web scraping toolkit."
        assert first["position"] == 1
        assert r.errors == []

    def test_missing_key_returns_helpful_error(self):
        s = GoogleSearchScraper()
        r = s.scrape(query="anything")
        assert r.data == []
        assert "SERPBASE_API_KEY" in r.errors[0].message
        assert "serpbase.dev" in r.errors[0].message

    def test_error_envelope_is_not_silent_empty(self):
        # The API answers 200 and signals failures through the envelope:
        # a non-zero status must surface as an error, not as "no results".
        payload = json.dumps({"status": 7, "error": "invalid api key"})
        s = _with(GoogleSearchScraper(api_key="bad"), payload)
        r = s.scrape(query="x")
        assert r.data == []
        assert "invalid api key" in r.errors[0].message

    def test_max_results_truncates(self):
        organic = [
            {
                "title": f"Result {i}",
                "link": f"https://example.com/{i}",
                "snippet": "",
                "position": i,
            }
            for i in range(1, 21)
        ]
        payload = json.dumps({"status": 0, "organic": organic})
        s = _with(GoogleSearchScraper(api_key="k"), payload)
        r = s.scrape(query="x", max_results=5)
        assert len(r.data) == 5
        assert r.data[-1]["position"] == 5

    def test_request_shape_and_headers(self):
        s = _with(GoogleSearchScraper(api_key="secret"), json.dumps({"status": 0, "organic": []}))
        s.scrape(query="hello world", language="en", country="us")
        args, kwargs = s._http.post_json.call_args
        assert args[0] == "https://api.serpbase.dev/google/search"
        assert kwargs["headers"] == {"X-API-Key": "secret"}
        assert kwargs["json"]["q"] == "hello world"
        assert kwargs["json"]["hl"] == "en"
        assert kwargs["json"]["gl"] == "us"
        # Locale params must be omitted when not requested (no empty defaults).
        s2 = _with(GoogleSearchScraper(api_key="k"), json.dumps({"status": 0, "organic": []}))
        s2.scrape(query="no locale")
        _, kwargs2 = s2._http.post_json.call_args
        assert "hl" not in kwargs2["json"]
        assert "gl" not in kwargs2["json"]

    def test_async_parse(self):
        import asyncio

        payload = json.dumps(
            {
                "status": 0,
                "organic": [
                    {
                        "title": "PyScrappy",
                        "link": "https://github.com/mldsveda/PyScrappy",
                        "snippet": "A robust Python web scraping toolkit.",
                        "position": 1,
                    }
                ],
            }
        )

        async def _fake_post_json(*args, **kwargs):
            return payload

        s = GoogleSearchScraper(api_key="k")
        s._async_http = MagicMock()
        s._async_http.post_json.side_effect = _fake_post_json
        r = asyncio.run(s.scrape_async(query="pyscrappy"))
        assert len(r.data) == 1
        assert r.data[0]["title"] == "PyScrappy"
