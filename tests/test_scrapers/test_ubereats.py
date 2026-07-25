"""Tests for pyscrappy.scrapers.ubereats."""

import json
from unittest.mock import MagicMock

from pyscrappy.scrapers.ubereats import UberEatsScraper

GEO_JSON = json.dumps({"results": [{
    "name": "London", "latitude": 51.5, "longitude": -0.12,
}]})

FEED_JSON = json.dumps({"data": {"cityName": "london", "feedItems": [
    {"type": "REGULAR_STORE", "store": {
        "storeUuid": "abc-123",
        "title": {"text": "Domino's Pizza"},
        "meta": [{"text": "£0.99 Delivery Fee"}, {"text": "20 min"}],
        "actionUrl": "/store/dominos/abc-123",
    }},
    {"type": "DIVIDER"},
    {"type": "REGULAR_STORE", "store": {
        "storeUuid": "def-456",
        "title": {"text": "Five Guys"},
        "meta": [{"text": "10 min"}],
        "actionUrl": "/store/five-guys/def-456",
    }},
]}})

STORE_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Restaurant","name":"Domino's Pizza",
 "servesCuisine":"Pizza","priceRange":"££",
 "aggregateRating":{"ratingValue":4.2,"reviewCount":500},
 "telephone":"+44 20 1234",
 "hasMenu":{"@type":"Menu","hasMenuSection":[
   {"@type":"MenuSection","name":"Pizzas","hasMenuItem":[
     {"@type":"MenuItem","name":"Pepperoni &amp; Cheese","description":"Classic",
      "offers":{"price":"12.99","priceCurrency":"GBP"}}
   ]}
 ]}}
</script>
</head><body></body></html>
"""


def _mock(scraper, *responses):
    scraper._http = MagicMock()
    scraper._http.get_html.side_effect = list(responses)
    scraper._http.post_json.return_value = responses[-1] if responses else ""
    scraper._http.set_cookie = MagicMock()
    return scraper


class TestUberEatsSearch:
    def test_lists_restaurants(self):
        s = UberEatsScraper()
        s._http = MagicMock()
        s._http.get_html.side_effect = [GEO_JSON]  # geocode + homepage
        s._http.get_html.return_value = GEO_JSON
        # geocode returns GEO_JSON; homepage returns anything; feed via post_json
        s._http.get_html.side_effect = [GEO_JSON, "<html></html>"]
        s._http.post_json.return_value = FEED_JSON
        s._http.set_cookie = MagicMock()

        result = s.scrape(city="London", max_results=10)
        assert len(result.data) == 2
        first = result.data[0]
        assert first["name"] == "Domino's Pizza"
        assert first["delivery_fee"] == "£0.99 Delivery Fee"
        assert first["eta"] == "20 min"
        # url gets the locale prefix for get_menu
        assert first["url"] == "https://www.ubereats.com/gb/store/dominos/abc-123"

    def test_city_not_found(self):
        s = UberEatsScraper()
        s._http = MagicMock()
        s._http.get_html.side_effect = [json.dumps({"results": []})]
        result = s.scrape(city="Nowhere")
        assert result.data == []
        assert "not found" in result.errors[0].message


class TestUberEatsMenu:
    def test_extracts_menu_from_jsonld(self):
        s = UberEatsScraper()
        s._http = MagicMock()
        s._http.get_html.return_value = STORE_HTML
        result = s.get_menu("https://www.ubereats.com/gb/store/dominos/abc-123")
        assert len(result.data) == 1
        rec = result.data[0]
        assert rec["name"] == "Domino's Pizza"
        assert rec["rating"] == 4.2
        assert rec["cuisine"] == "Pizza"
        assert len(rec["menu"]) == 1
        item = rec["menu"][0]
        assert item["name"] == "Pepperoni & Cheese"  # HTML-unescaped
        assert item["price"] == "12.99"
        assert item["currency"] == "GBP"
        assert item["section"] == "Pizzas"

    def test_no_jsonld_reports_error(self):
        s = UberEatsScraper()
        s._http = MagicMock()
        s._http.get_html.return_value = "<html><body>no data</body></html>"
        result = s.get_menu("https://www.ubereats.com/gb/store/x/y")
        assert result.data == []
        assert result.errors
