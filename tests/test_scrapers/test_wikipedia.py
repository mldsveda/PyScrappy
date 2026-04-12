"""Tests for pyscrappy.scrapers.wikipedia."""

from unittest.mock import MagicMock

import pytest

from pyscrappy.core.models import ScrapeResult
from pyscrappy.scrapers.wikipedia import WikipediaScraper

SAMPLE_WIKI_HTML = """
<html>
<body>
<div id="mw-content-text">
<div class="mw-parser-output">
    <table class="infobox">
        <tr><th>Language</th><td>Python</td></tr>
        <tr><th>Paradigm</th><td>Multi-paradigm</td></tr>
    </table>
    <p>Python is a high-level programming language. [1] It was created by Guido van Rossum. [2]</p>
    <p>Short</p>
    <h2><span class="mw-headline" id="History">History</span></h2>
    <p>Python was conceived in the late 1980s by Guido van Rossum at CWI in the Netherlands. [3]</p>
    <h3><span class="mw-headline" id="Version_3">Version 3</span></h3>
    <p>Python 3.0 was released on December 3, 2008. [4] It was a major revision not fully backward-compatible.</p>
    <table class="wikitable">
        <tr><th>Version</th><th>Release Date</th></tr>
        <tr><td>3.0</td><td>2008-12-03</td></tr>
        <tr><td>3.9</td><td>2020-10-05</td></tr>
    </table>
</div>
</div>
</body>
</html>
"""

EMPTY_WIKI_HTML = """
<html><body><div id="content"><p>No article found.</p></div></body></html>
"""


class TestWikipediaScraperInit:
    def test_default_lang(self):
        scraper = WikipediaScraper()
        assert scraper._lang == "en"
        assert scraper._base == "https://en.wikipedia.org/wiki/"
        assert scraper.name == "wikipedia"

    def test_custom_lang(self):
        scraper = WikipediaScraper(lang="fr")
        assert scraper._lang == "fr"
        assert scraper._base == "https://fr.wikipedia.org/wiki/"


class TestWikipediaScraperFull:
    def test_full_mode(self):
        scraper = WikipediaScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_WIKI_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="Python (programming language)")

        assert isinstance(result, ScrapeResult)
        assert len(result.data) > 0
        assert result.metadata.scraper == "wikipedia"

        # Should have infobox
        infobox_items = [d for d in result.data if d.get("type") == "infobox"]
        assert len(infobox_items) == 1
        assert infobox_items[0]["data"]["Language"] == "Python"

        # Should have headers
        header_items = [d for d in result.data if d.get("type") == "header"]
        assert any(h["text"] == "History" for h in header_items)

        # Should have paragraphs without bracket citations
        para_items = [d for d in result.data if d.get("type") == "paragraph"]
        assert len(para_items) > 0
        for p in para_items:
            assert "[1]" not in p["text"]
            assert "[2]" not in p["text"]

        # Should have tables
        table_items = [d for d in result.data if d.get("type") == "table"]
        assert len(table_items) == 1
        assert table_items[0]["data"][0]["Version"] == "3.0"
        scraper.close()


class TestWikipediaScraperModes:
    def test_paragraphs_mode(self):
        scraper = WikipediaScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_WIKI_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="Python", mode="paragraphs")
        assert all(d["type"] == "paragraph" for d in result.data)
        assert len(result.data) > 0
        scraper.close()

    def test_headers_mode(self):
        scraper = WikipediaScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_WIKI_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="Python", mode="headers")
        assert all(d["type"] == "header" for d in result.data)
        assert any(d["text"] == "History" for d in result.data)
        assert any(d["text"] == "Version 3" for d in result.data)
        scraper.close()

    def test_summary_mode(self):
        scraper = WikipediaScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_WIKI_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="Python", mode="summary")
        assert len(result.data) == 1
        assert result.data[0]["type"] == "summary"
        assert "Python" in result.data[0]["text"]
        scraper.close()


class TestWikipediaScraperEdgeCases:
    def test_missing_content_div(self):
        scraper = WikipediaScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = EMPTY_WIKI_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="NonExistentArticle")
        assert result.data == []
        scraper.close()

    def test_clean_text_removes_brackets(self):
        scraper = WikipediaScraper()
        assert scraper._clean_text("Hello [1] World [citation needed]") == "Hello World"

    def test_clean_text_normalizes_whitespace(self):
        scraper = WikipediaScraper()
        assert scraper._clean_text("  Hello   World  ") == "Hello World"

    def test_url_encoding(self):
        scraper = WikipediaScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SAMPLE_WIKI_HTML
        scraper._http = mock_http

        scraper.scrape(query="Python (programming language)")
        call_url = mock_http.get_html.call_args[0][0]
        assert "Python_%28programming_language%29" in call_url
        scraper.close()
