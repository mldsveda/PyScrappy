"""Tests for food delivery scrapers: Zomato."""

import json
from unittest.mock import MagicMock

from pyscrappy.scrapers.zomato import ZomatoScraper

# --- Zomato ---

ZOMATO_NEXT_DATA = {
    "props": {
        "pageProps": {
            "sections": [{
                "cards": [{
                    "info": {
                        "id": "67890",
                        "name": "Biryani House",
                        "cuisine_string": "Biryani, North Indian",
                        "rating": {"aggregate_rating": "4.3"},
                        "average_cost_for_two": 600,
                        "location": {"address": "123 Main St, Mumbai"},
                    }
                }]
            }]
        }
    }
}

ZOMATO_HTML_JSON = (
    '<html><body>'
    '<script id="__NEXT_DATA__" type="application/json">'
    + json.dumps(ZOMATO_NEXT_DATA)
    + '</script></body></html>'
)

ZOMATO_HTML_RENDERED = """
<html><body>
<a href="/order/biryani-house-67890">
    <h4>Tandoori Flames</h4>
    <div class="sc-rating">4.1</div>
    <div class="sc-cuisine">North Indian, Tandoor</div>
</a>
</body></html>
"""


class TestZomatoScraper:
    def test_name(self):
        assert ZomatoScraper().name == "zomato"

    def test_extract_from_next_data(self):
        scraper = ZomatoScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = ZOMATO_HTML_JSON
        scraper._http = mock_http

        result = scraper.scrape(city="mumbai")

        assert len(result.data) == 1
        restaurant = result.data[0]
        assert restaurant["name"] == "Biryani House"
        assert restaurant["cuisine"] == "Biryani, North Indian"
        assert restaurant["rating"] == "4.3"
        assert restaurant["price"] == 600
        assert restaurant["address"] == "123 Main St, Mumbai"
        scraper.close()

    def test_html_fallback(self):
        scraper = ZomatoScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = ZOMATO_HTML_RENDERED
        scraper._http = mock_http

        result = scraper.scrape(city="mumbai")
        assert len(result.data) >= 1
        scraper.close()

    def test_no_restaurants_adds_error(self):
        scraper = ZomatoScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        result = scraper.scrape(city="testcity")
        assert len(result.errors) == 1
        assert "No restaurants extracted" in result.errors[0].message
        scraper.close()

    def test_city_url(self):
        scraper = ZomatoScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(city="New Delhi")
        url = mock_http.get_html.call_args[0][0]
        assert "zomato.com/new-delhi/delivery" in url
        scraper.close()

    def test_query_url(self):
        scraper = ZomatoScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(city="bangalore", query="pizza")
        url = mock_http.get_html.call_args[0][0]
        assert "zomato.com/bangalore/search" in url
        assert "q=pizza" in url
        scraper.close()
