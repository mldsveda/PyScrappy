"""Tests for e-commerce scrapers: Amazon."""

from unittest.mock import MagicMock

from pyscrappy.scrapers.amazon import AmazonScraper
from pyscrappy.scrapers.ikea import IKEAScraper
from pyscrappy.scrapers.newegg import NeweggScraper

# --- Amazon ---

AMAZON_HTML = """
<html><body>
<div data-component-type="s-search-result">
    <h2><a href="/dp/B09V3KXJPB/ref=sr_1"><span>Sony WH-1000XM5</span></a></h2>
    <span class="a-price-whole">348.</span>
    <span class="a-price-fraction">00</span>
    <span class="a-price a-text-price"><span class="a-offscreen">$399.99</span></span>
    <span class="a-icon-alt">4.5 out of 5 stars</span>
    <span class="a-size-base s-underline-text">12,345</span>
    <img class="s-image" src="https://img.amazon.com/headphones.jpg">
</div>
</body></html>
"""

AMAZON_CAPTCHA_HTML = """
<html><body>
<form action="/errors/validateCaptcha">
    <input type="text" name="captcha">
</form>
</body></html>
"""


class TestAmazonScraper:
    def test_name(self):
        assert AmazonScraper().name == "amazon"

    def test_custom_domain(self):
        scraper = AmazonScraper(domain="www.amazon.in")
        assert scraper._domain == "www.amazon.in"

    def test_parse_search_results(self):
        scraper = AmazonScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = AMAZON_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="headphones")

        assert len(result.data) == 1
        product = result.data[0]
        assert product["title"] == "Sony WH-1000XM5"
        assert product["price"] == "348.00"
        assert product["original_price"] == "$399.99"
        assert product["rating"] == "4.5"
        assert product["review_count"] == "12345"
        assert product["image"] == "https://img.amazon.com/headphones.jpg"
        scraper.close()

    def test_captcha_detection(self):
        scraper = AmazonScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = AMAZON_CAPTCHA_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        assert "CAPTCHA" in result.errors[0].message
        scraper.close()

    def test_pagination_urls(self):
        empty = "<html><body></body></html>"
        scraper = AmazonScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = [AMAZON_HTML, empty]
        scraper._http = mock_http

        scraper.scrape(query="test", max_pages=2)
        calls = mock_http.get_html.call_args_list
        assert "page=1" in calls[0][0][0]
        assert "page=2" in calls[1][0][0]
        scraper.close()

    def test_fetch_error(self):
        scraper = AmazonScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = Exception("timeout")
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        scraper.close()


# --- Newegg ---

NEWEGG_HTML = """
<html><body>
<div class="item-cell">
    <a class="item-title" href="https://www.newegg.com/p/ABC123?item=1">
        ASUS ROG Strix Graphics Card
    </a>
    <li class="price-current">$669.99–</li>
    <span class="item-rating" aria-label="rated 4.5 out of 5"></span>
    <span class="item-rating-num">(123)</span>
    <a class="item-img"><img src="https://img.newegg.com/gpu.jpg"></a>
</div>
</body></html>
"""


class TestNeweggScraper:
    def test_name(self):
        assert NeweggScraper().name == "newegg"

    def test_parse_results(self):
        scraper = NeweggScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = NEWEGG_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="graphics card")
        assert len(result.data) == 1
        p = result.data[0]
        assert p["title"] == "ASUS ROG Strix Graphics Card"
        assert p["price"] == "$669.99"
        assert p["rating"] == "4.5"
        assert p["review_count"] == "123"
        assert p["image"] == "https://img.newegg.com/gpu.jpg"
        scraper.close()

    def test_empty_reports_error(self):
        scraper = NeweggScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        result = scraper.scrape(query="zzz")
        assert result.data == []
        assert result.errors
        scraper.close()


# --- IKEA ---

IKEA_JSON = """
{
  "searchResultPage": {
    "products": {
      "main": {
        "items": [
          {"product": {
            "name": "LAGKAPTEN / ALEX",
            "typeName": "Desk",
            "id": "s99431982",
            "salesPrice": {"numeral": 239.99, "prefix": "$"},
            "pipUrl": "https://www.ikea.com/us/en/p/lagkapten-alex-desk-s99431982/",
            "mainImageUrl": "https://www.ikea.com/img/desk.jpg",
            "ratingValue": 4.5,
            "ratingCount": 200
          }}
        ]
      }
    }
  }
}
"""


class TestIKEAScraper:
    def test_name(self):
        assert IKEAScraper().name == "ikea"

    def test_parse_products(self):
        scraper = IKEAScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = IKEA_JSON
        scraper._http = mock_http

        result = scraper.scrape(query="desk")
        assert len(result.data) == 1
        p = result.data[0]
        assert p["name"] == "LAGKAPTEN / ALEX"
        assert p["type"] == "Desk"
        assert p["price"] == 239.99
        assert p["currency"] == "$"
        assert p["rating"] == 4.5
        assert p["url"].endswith("s99431982/")
        scraper.close()

    def test_empty_reports_error(self):
        scraper = IKEAScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = (
            '{"searchResultPage": {"products": {"main": {"items": []}}}}'
        )
        scraper._http = mock_http

        result = scraper.scrape(query="zzz")
        assert result.data == []
        assert result.errors
        scraper.close()

    def test_bad_json_reports_error(self):
        scraper = IKEAScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "not json"
        scraper._http = mock_http

        result = scraper.scrape(query="desk")
        assert result.data == []
        assert result.errors
        scraper.close()
