"""Tests for pyscrappy.core.base."""

from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.http import HttpClient
from pyscrappy.core.models import ScrapeResult


class ConcreteScraper(BaseScraper):
    """Concrete implementation for testing the abstract base."""

    name = "test_scraper"

    def scrape(self, **kwargs):
        return ScrapeResult(data=[{"test": True}])


class TestBaseScraperInit:
    def test_default_config(self):
        scraper = ConcreteScraper()
        assert scraper.config.timeout == 30.0
        assert scraper._http is None
        assert scraper._browser is None

    def test_custom_config(self):
        config = ScraperConfig(timeout=10.0)
        scraper = ConcreteScraper(config)
        assert scraper.config.timeout == 10.0

    def test_name_attribute(self):
        scraper = ConcreteScraper()
        assert scraper.name == "test_scraper"

    def test_logger_name(self):
        scraper = ConcreteScraper()
        assert scraper.logger.name == "pyscrappy.test_scraper"


class TestBaseScraperContextManager:
    def test_enter_returns_self(self):
        scraper = ConcreteScraper()
        result = scraper.__enter__()
        assert result is scraper
        scraper.__exit__(None, None, None)

    def test_exit_closes_resources(self):
        scraper = ConcreteScraper()
        mock_http = MagicMock()
        mock_browser = MagicMock()
        scraper._http = mock_http
        scraper._browser = mock_browser

        scraper.__exit__(None, None, None)

        mock_http.close.assert_called_once()
        mock_browser.close.assert_called_once()
        assert scraper._http is None
        assert scraper._browser is None

    def test_with_statement(self):
        with ConcreteScraper() as scraper:
            assert isinstance(scraper, ConcreteScraper)


class TestBaseScraperLazyProperties:
    def test_http_property_creates_lazily(self):
        scraper = ConcreteScraper()
        assert scraper._http is None
        http = scraper.http
        assert isinstance(http, HttpClient)
        assert scraper._http is http
        scraper.close()

    def test_http_property_reuses_instance(self):
        scraper = ConcreteScraper()
        http1 = scraper.http
        http2 = scraper.http
        assert http1 is http2
        scraper.close()


class TestBaseScraperClose:
    def test_close_when_nothing_initialized(self):
        scraper = ConcreteScraper()
        scraper.close()  # should not raise

    def test_close_cleans_http(self):
        scraper = ConcreteScraper()
        mock_http = MagicMock()
        scraper._http = mock_http
        scraper.close()
        mock_http.close.assert_called_once()
        assert scraper._http is None

    def test_close_cleans_browser(self):
        scraper = ConcreteScraper()
        mock_browser = MagicMock()
        scraper._browser = mock_browser
        scraper.close()
        mock_browser.close.assert_called_once()
        assert scraper._browser is None


class TestBaseScraperParseHtml:
    def test_parse_html_returns_beautifulsoup(self):
        scraper = ConcreteScraper()
        soup = scraper.parse_html("<html><body><p>Hello</p></body></html>")
        assert isinstance(soup, BeautifulSoup)
        assert soup.find("p").get_text() == "Hello"


class TestBaseScraperFetchHtml:
    def test_fetch_html_plain(self):
        scraper = ConcreteScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html>plain</html>"
        scraper._http = mock_http

        html = scraper.fetch_html("https://example.com")
        assert html == "<html>plain</html>"
        mock_http.get_html.assert_called_once_with("https://example.com")
        scraper.close()

    def test_fetch_html_with_js(self):
        scraper = ConcreteScraper()
        mock_browser = MagicMock()
        mock_browser.get_html.return_value = "<html>rendered</html>"
        scraper._browser = mock_browser

        html = scraper.fetch_html("https://example.com", render_js=True)
        assert html == "<html>rendered</html>"
        scraper.close()


class TestBaseScraperFetchAndParse:
    def test_fetch_and_parse(self):
        scraper = ConcreteScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body><h1>Title</h1></body></html>"
        scraper._http = mock_http

        soup = scraper.fetch_and_parse("https://example.com")
        assert isinstance(soup, BeautifulSoup)
        assert soup.find("h1").get_text() == "Title"
        scraper.close()


class TestBaseScraperAbstract:
    def test_cannot_instantiate_without_scrape(self):
        with pytest.raises(TypeError):
            BaseScraper()
