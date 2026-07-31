"""Tests for pyscrappy.generic.pagination."""

from bs4 import BeautifulSoup

from pyscrappy.generic.pagination import (
    _extract_page_number,
    _find_page_number_links,
    find_next_page_url,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


class TestFindNextPageUrl:
    def test_link_rel_next(self):
        soup = _soup('<html><head><link rel="next" href="/page/2"></head></html>')
        result = find_next_page_url(soup, "https://example.com/page/1")
        assert result == "https://example.com/page/2"

    def test_next_text_link(self):
        soup = _soup('<html><body><a href="/page/2">Next</a></body></html>')
        result = find_next_page_url(soup, "https://example.com/page/1")
        assert result == "https://example.com/page/2"

    def test_next_arrow_link(self):
        soup = _soup('<html><body><a href="/page/2">></a></body></html>')
        result = find_next_page_url(soup, "https://example.com/page/1")
        assert result == "https://example.com/page/2"

    def test_next_double_arrow(self):
        soup = _soup('<html><body><a href="/page/2">\u00bb</a></body></html>')
        result = find_next_page_url(soup, "https://example.com/page/1")
        assert result == "https://example.com/page/2"

    def test_next_page_text(self):
        soup = _soup('<html><body><a href="?page=2">Next Page</a></body></html>')
        result = find_next_page_url(soup, "https://example.com?page=1")
        assert result == "https://example.com?page=2"

    def test_aria_label_next(self):
        soup = _soup('<html><body><a href="/p/2" aria-label="Next page">2</a></body></html>')
        result = find_next_page_url(soup, "https://example.com/p/1")
        assert result is not None

    def test_next_class_with_page_url(self):
        soup = _soup('<html><body><a href="?page=3" class="next-btn">3</a></body></html>')
        result = find_next_page_url(soup, "https://example.com?page=2")
        assert result == "https://example.com?page=3"

    def test_numbered_pagination(self):
        soup = _soup(
            "<html><body>"
            '<a href="?page=1">1</a>'
            '<a href="?page=2">2</a>'
            '<a href="?page=3">3</a>'
            "</body></html>"
        )
        result = find_next_page_url(soup, "https://example.com?page=2")
        assert result == "https://example.com?page=3"

    def test_no_next_page(self):
        soup = _soup('<html><body><a href="/about">About</a></body></html>')
        result = find_next_page_url(soup, "https://example.com/page/5")
        assert result is None

    def test_load_more_text(self):
        soup = _soup('<html><body><a href="?page=2">Load More</a></body></html>')
        result = find_next_page_url(soup, "https://example.com?page=1")
        assert result == "https://example.com?page=2"


class TestExtractPageNumber:
    def test_page_param(self):
        assert _extract_page_number("https://example.com?page=3") == 3

    def test_p_param(self):
        assert _extract_page_number("https://example.com?p=5") == 5

    def test_pg_param(self):
        assert _extract_page_number("https://example.com?pg=10") == 10

    def test_page_path(self):
        assert _extract_page_number("https://example.com/page/7") == 7

    def test_no_page_number(self):
        assert _extract_page_number("https://example.com/about") is None

    def test_page_param_with_other_params(self):
        assert _extract_page_number("https://example.com?q=test&page=2&sort=new") == 2


class TestFindPageNumberLinks:
    def test_finds_pagination_links(self):
        soup = _soup(
            "<html><body>"
            '<a href="?page=1">1</a>'
            '<a href="?page=2">2</a>'
            '<a href="?page=3">3</a>'
            "</body></html>"
        )
        result = _find_page_number_links(soup, "https://example.com")
        assert len(result) == 3
        assert result[0] == (1, "https://example.com?page=1")
        assert result[2] == (3, "https://example.com?page=3")

    def test_ignores_non_pagination_links(self):
        soup = _soup('<html><body><a href="/about">About</a><a href="?page=2">2</a></body></html>')
        result = _find_page_number_links(soup, "https://example.com")
        assert len(result) == 1

    def test_empty_page(self):
        soup = _soup("<html><body></body></html>")
        result = _find_page_number_links(soup, "https://example.com")
        assert result == []
