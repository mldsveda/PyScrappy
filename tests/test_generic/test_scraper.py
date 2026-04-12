"""Tests for pyscrappy.generic.scraper."""

from unittest.mock import MagicMock, patch

import pytest

from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeResult
from pyscrappy.generic.scraper import GenericScraper


SAMPLE_HTML = """
<html lang="en">
<head>
    <title>Test Page</title>
    <meta name="description" content="A test page for scraping">
    <meta property="og:title" content="OG Test">
</head>
<body>
    <h1>Main Heading</h1>
    <article>
        <p>This is a long enough paragraph that should be extracted by the text extractor component.</p>
        <p>Another paragraph with sufficient content to pass the minimum length threshold for extraction.</p>
    </article>
    <a href="https://example.com/link1">Link One</a>
    <a href="/link2">Link Two</a>
    <img src="https://example.com/image.jpg" alt="Test image">
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>Alpha</td><td>100</td></tr>
    </table>
</body>
</html>
"""


class TestGenericScraperInit:
    def test_name(self):
        scraper = GenericScraper()
        assert scraper.name == "generic"

    def test_has_extractors(self):
        scraper = GenericScraper()
        assert scraper._metadata_extractor is not None
        assert scraper._text_extractor is not None
        assert scraper._link_extractor is not None
        assert scraper._image_extractor is not None
        assert scraper._table_extractor is not None


class TestGenericScraperScrape:
    def test_scrape_single_page(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")

        assert isinstance(result, ScrapeResult)
        assert len(result.data) == 1
        data = result.data[0]
        assert data["url"] == "https://example.com"
        assert "metadata" in data
        assert "text" in data
        assert "links" in data
        assert "images" in data
        assert "tables" in data
        scraper.close()

    def test_scrape_extracts_metadata(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")
        metadata = result.data[0]["metadata"]
        assert metadata["title"] == "Test Page"
        assert metadata["description"] == "A test page for scraping"
        scraper.close()

    def test_scrape_extracts_text(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")
        text = result.data[0]["text"]
        assert text["word_count"] > 0
        assert len(text["paragraphs"]) >= 1
        scraper.close()

    def test_scrape_extracts_links(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")
        links = result.data[0]["links"]
        assert len(links) >= 1
        urls = [l["url"] for l in links]
        assert "https://example.com/link1" in urls
        scraper.close()

    def test_scrape_extracts_images(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")
        images = result.data[0]["images"]
        assert len(images) >= 1
        assert images[0]["url"] == "https://example.com/image.jpg"
        scraper.close()

    def test_scrape_extracts_tables(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")
        tables = result.data[0]["tables"]
        assert len(tables) >= 1
        assert tables[0][0] == {"Name": "Alpha", "Value": "100"}
        scraper.close()

    def test_scrape_metadata_populated(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")
        assert result.metadata.scraper == "generic"
        assert result.metadata.source_urls == ["https://example.com"]
        assert result.metadata.total_pages == 1
        scraper.close()


class TestGenericScraperWithSelectors:
    def test_custom_selectors(self):
        html = """
        <html><body>
            <h2 class="product-title">Product A</h2>
            <span class="price">$10</span>
            <h2 class="product-title">Product B</h2>
            <span class="price">$20</span>
        </body></html>
        """
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = html
        scraper._http = mock_http

        result = scraper.scrape(
            url="https://example.com",
            selectors={"name": "h2.product-title", "price": "span.price"},
        )

        assert len(result.data) == 2
        assert result.data[0]["name"] == "Product A"
        assert result.data[0]["price"] == "$10"
        assert result.data[1]["name"] == "Product B"
        assert result.data[1]["price"] == "$20"
        scraper.close()

    def test_selectors_with_uneven_matches(self):
        html = """
        <html><body>
            <h2 class="title">Item 1</h2>
            <h2 class="title">Item 2</h2>
            <span class="price">$5</span>
        </body></html>
        """
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = html
        scraper._http = mock_http

        result = scraper.scrape(
            url="https://example.com",
            selectors={"name": "h2.title", "price": "span.price"},
        )

        assert len(result.data) == 2
        assert result.data[0]["name"] == "Item 1"
        assert result.data[0]["price"] == "$5"
        assert result.data[1]["name"] == "Item 2"
        assert result.data[1]["price"] == ""  # padded
        scraper.close()

    def test_selectors_add_source_url(self):
        html = '<html><body><h1 class="t">Title</h1></body></html>'
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = html
        scraper._http = mock_http

        result = scraper.scrape(
            url="https://example.com",
            selectors={"title": "h1.t"},
        )
        assert result.data[0]["_source_url"] == "https://example.com"
        scraper.close()


class TestGenericScraperPagination:
    def test_multi_page_scrape(self):
        page1 = """
        <html><body>
            <p>Page 1 content that is long enough to be captured by the text extractor.</p>
            <a href="/page/2">Next</a>
        </body></html>
        """
        page2 = """
        <html><body>
            <p>Page 2 content that is long enough to be captured by the text extractor.</p>
        </body></html>
        """
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = [page1, page2]
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com/page/1", max_pages=2)

        assert len(result.data) == 2
        assert result.metadata.total_pages == 2
        assert len(result.metadata.source_urls) == 2
        scraper.close()

    def test_stops_when_no_next_page(self):
        page1 = "<html><body><p>Only page with long enough content for the extractor.</p></body></html>"
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = page1
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com", max_pages=5)

        assert result.metadata.total_pages == 1
        scraper.close()


class TestGenericScraperErrorHandling:
    def test_fetch_error_added_to_errors(self):
        scraper = GenericScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = Exception("connection timeout")
        scraper._http = mock_http

        result = scraper.scrape(url="https://example.com")

        assert len(result.errors) == 1
        assert "connection timeout" in result.errors[0].message
        assert result.data == []
        scraper.close()


class TestGenericScraperJsDetection:
    def test_looks_like_js_rendered_minimal_body(self):
        scraper = GenericScraper()
        html = """
        <html><body>
            <script>var a=1;</script>
            <script>var b=2;</script>
            <script>var c=3;</script>
            <script>var d=4;</script>
            <div id="root"></div>
        </body></html>
        """
        assert scraper._looks_like_js_rendered(html) is True

    def test_not_js_rendered_with_content(self):
        scraper = GenericScraper()
        html = """
        <html><body>
            <h1>Full Server-Rendered Page</h1>
            <p>This page has plenty of text content that indicates it was fully
            rendered on the server side and does not require JavaScript to display
            the main content to users. The text extractor should have no trouble
            extracting meaningful content from this page.</p>
            <p>More content here to make the body text substantial.</p>
            <p>Even more content to ensure the heuristic passes correctly.</p>
        </body></html>
        """
        assert scraper._looks_like_js_rendered(html) is False

    def test_looks_like_js_rendered_empty_root_div(self):
        scraper = GenericScraper()
        html = '<html><body><div id="root"></div></body></html>'
        assert scraper._looks_like_js_rendered(html) is True

    def test_looks_like_js_rendered_empty_app_div(self):
        scraper = GenericScraper()
        html = '<html><body><div id="app"></div></body></html>'
        assert scraper._looks_like_js_rendered(html) is True

    def test_looks_like_js_rendered_next_div(self):
        scraper = GenericScraper()
        html = '<html><body><div id="__next"></div></body></html>'
        assert scraper._looks_like_js_rendered(html) is True

    def test_no_body_returns_true(self):
        scraper = GenericScraper()
        html = "<html></html>"
        assert scraper._looks_like_js_rendered(html) is True


class TestConvenienceFunction:
    def test_scrape_function(self):
        from pyscrappy import scrape

        with patch.object(GenericScraper, "scrape") as mock_scrape:
            mock_scrape.return_value = ScrapeResult(data=[{"test": True}])
            result = scrape("https://example.com")
            assert len(result.data) == 1
