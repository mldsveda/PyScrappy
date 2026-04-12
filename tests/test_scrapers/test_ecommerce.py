"""Tests for e-commerce scrapers: Amazon, Flipkart, Alibaba, Snapdeal."""

from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from pyscrappy.scrapers.amazon import AmazonScraper
from pyscrappy.scrapers.alibaba import AlibabaScraper
from pyscrappy.scrapers.flipkart import FlipkartScraper
from pyscrappy.scrapers.snapdeal import SnapdealScraper

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

        result = scraper.scrape(query="test", max_pages=2)
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


# --- Flipkart ---

FLIPKART_HTML = """
<html><body>
<div data-id="PROD123">
    <a class="wjcEIp" title="Samsung Galaxy S24">Samsung Galaxy S24</a>
    <a href="/samsung-galaxy-s24/p/itm123?pid=PROD123">Link</a>
    <div class="Nx9bqj">₹79,999</div>
    <div class="yRaY8j">₹89,999</div>
    <div class="XQDdHH">4.5</div>
    <ul class="G4BRas"><li>128GB Storage</li><li>8GB RAM</li></ul>
</div>
</body></html>
"""


class TestFlipkartScraper:
    def test_name(self):
        assert FlipkartScraper().name == "flipkart"

    def test_parse_results(self):
        scraper = FlipkartScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = FLIPKART_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="samsung galaxy")

        assert len(result.data) == 1
        product = result.data[0]
        assert product["name"] == "Samsung Galaxy S24"
        assert product["price"] == "₹79,999"
        assert product["original_price"] == "₹89,999"
        assert product["rating"] == "4.5"
        assert "128GB Storage" in product["description"]
        scraper.close()

    def test_max_pages_validation(self):
        scraper = FlipkartScraper()
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            scraper.scrape(query="test", max_pages=0)

    def test_url_format(self):
        scraper = FlipkartScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(query="laptop bag")
        url = mock_http.get_html.call_args[0][0]
        assert "flipkart.com/search" in url
        assert "q=laptop+bag" in url
        scraper.close()


# --- Alibaba ---

ALIBABA_HTML = """
<html><body>
<div class="organic-gallery-offer-outter">
    <h2 class="title"><a title="Bluetooth Speaker Portable">Bluetooth Speaker</a></h2>
    <a href="//www.alibaba.com/product/123">Link</a>
    <div class="elements-offer-price-normal">$5.99 - $12.99</div>
    <div class="element-offer-minorder-normal">100 Pieces</div>
    <div class="seb-supplier-review__rating">4.8</div>
    <div class="seb-supplier">Shenzhen Audio Co.</div>
</div>
</body></html>
"""


class TestAlibabaScraper:
    def test_name(self):
        assert AlibabaScraper().name == "alibaba"

    def test_parse_results(self):
        scraper = AlibabaScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = ALIBABA_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="bluetooth speaker")

        assert len(result.data) == 1
        product = result.data[0]
        assert product["name"] == "Bluetooth Speaker"
        assert product["price"] == "$5.99 - $12.99"
        assert product["min_order"] == "100 Pieces"
        assert product["rating"] == "4.8"
        assert product["supplier"] == "Shenzhen Audio Co."
        scraper.close()

    def test_max_pages_validation(self):
        scraper = AlibabaScraper()
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            scraper.scrape(query="test", max_pages=0)

    def test_url_protocol_fix(self):
        scraper = AlibabaScraper()
        soup = BeautifulSoup(ALIBABA_HTML, "lxml")
        card = soup.select_one(".organic-gallery-offer-outter")
        product = scraper._parse_card(card)
        assert product["url"].startswith("https://")


# --- Snapdeal ---

SNAPDEAL_HTML = """
<html><body>
<div class="product-tuple-listing">
    <p class="product-title">Boat Rockerz 450</p>
    <a href="//www.snapdeal.com/product/boat-rockerz/123">Link</a>
    <span class="product-price">Rs. 999</span>
    <span class="product-desc-price">Rs. 2,999</span>
    <div class="product-rating-count">4.2</div>
</div>
</body></html>
"""


class TestSnapdealScraper:
    def test_name(self):
        assert SnapdealScraper().name == "snapdeal"

    def test_parse_results(self):
        scraper = SnapdealScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SNAPDEAL_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="headphones")

        assert len(result.data) == 1
        product = result.data[0]
        assert product["name"] == "Boat Rockerz 450"
        assert product["price"] == "Rs. 999"
        assert product["original_price"] == "Rs. 2,999"
        assert product["rating"] == "4.2"
        scraper.close()

    def test_max_pages_validation(self):
        scraper = SnapdealScraper()
        with pytest.raises(ValueError, match="max_pages must be >= 1"):
            scraper.scrape(query="test", max_pages=0)

    def test_url_protocol_fix(self):
        scraper = SnapdealScraper()
        soup = BeautifulSoup(SNAPDEAL_HTML, "lxml")
        card = soup.select_one(".product-tuple-listing")
        product = scraper._parse_card(card)
        assert product["url"].startswith("https://")
