"""Tests for pyscrappy.scrapers.imdb."""

from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from pyscrappy.core.models import ScrapeResult
from pyscrappy.scrapers.imdb import IMDBScraper, _VALID_GENRES

CHART_HTML = """
<html><body>
<ul>
    <li class="ipc-metadata-list-summary-item">
        <h3 class="ipc-title__text">1. The Shawshank Redemption</h3>
        <a class="ipc-title-link-wrapper" href="/title/tt0111161/?ref_=top">Link</a>
        <span class="cli-title-metadata-item">1994</span>
        <span class="cli-title-metadata-item">2h 22min</span>
        <span class="cli-title-metadata-item">R</span>
        <span class="ipc-rating-star--rating">9.3</span>
        <span class="ipc-rating-star--voteCount">(2.8M)</span>
    </li>
    <li class="ipc-metadata-list-summary-item">
        <h3 class="ipc-title__text">2. The Godfather</h3>
        <a class="ipc-title-link-wrapper" href="/title/tt0068646/?ref_=top">Link</a>
        <span class="cli-title-metadata-item">1972</span>
        <span class="ipc-rating-star--rating">9.2</span>
    </li>
</ul>
</body></html>
"""

SEARCH_HTML = """
<html><body>
<div class="ipc-metadata-list-summary-item">
    <h3 class="ipc-title__text">Inception</h3>
    <a class="ipc-title-link-wrapper" href="/title/tt1375666/?ref_=adv">Link</a>
    <span class="cli-title-metadata-item">2010</span>
    <span class="ipc-rating-star--rating">8.8</span>
</div>
</body></html>
"""


class TestIMDBScraperInit:
    def test_name(self):
        scraper = IMDBScraper()
        assert scraper.name == "imdb"


class TestIMDBScraperValidation:
    def test_no_args_raises(self):
        scraper = IMDBScraper()
        with pytest.raises(ValueError, match="Provide at least one"):
            scraper.scrape()

    def test_invalid_genre_raises(self):
        scraper = IMDBScraper()
        with pytest.raises(ValueError, match="Unknown genre"):
            scraper.scrape(genre="nonexistent")

    def test_invalid_chart_raises(self):
        scraper = IMDBScraper()
        mock_http = MagicMock()
        scraper._http = mock_http
        with pytest.raises(ValueError, match="Unknown chart"):
            scraper.scrape(chart="invalid")
        scraper.close()

    def test_valid_genres(self):
        expected = {
            "action", "adventure", "animation", "biography", "comedy", "crime",
            "documentary", "drama", "family", "fantasy", "film-noir", "history",
            "horror", "music", "musical", "mystery", "romance", "sci-fi",
            "sport", "thriller", "war", "western",
        }
        assert _VALID_GENRES == expected


class TestIMDBScraperChart:
    def test_parse_chart_items(self):
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = CHART_HTML
        scraper._http = mock_http

        result = scraper.scrape(chart="top250")

        assert isinstance(result, ScrapeResult)
        assert len(result.data) == 2
        assert result.data[0]["title"] == "1. The Shawshank Redemption"
        assert result.data[0]["year"] == "1994"
        assert result.data[0]["rating"] == "9.3"
        assert result.data[0]["votes"] == "2.8M"
        assert "/title/tt0111161/" in result.data[0]["url"]
        scraper.close()

    def test_chart_url_top250(self):
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = CHART_HTML
        scraper._http = mock_http

        scraper.scrape(chart="top250")
        url = mock_http.get_html.call_args[0][0]
        assert "/chart/top/" in url
        scraper.close()

    def test_chart_url_popular(self):
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = CHART_HTML
        scraper._http = mock_http

        scraper.scrape(chart="popular")
        url = mock_http.get_html.call_args[0][0]
        assert "/chart/moviemeter/" in url
        scraper.close()


class TestIMDBScraperSearch:
    def test_search_by_query(self):
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SEARCH_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="inception")

        assert len(result.data) == 1
        assert result.data[0]["title"] == "Inception"
        assert result.data[0]["year"] == "2010"
        scraper.close()

    def test_search_by_genre(self):
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SEARCH_HTML
        scraper._http = mock_http

        result = scraper.scrape(genre="sci-fi")

        url = mock_http.get_html.call_args[0][0]
        assert "genres=sci-fi" in url
        assert "title_type=feature" in url
        scraper.close()

    def test_search_pagination_url(self):
        empty_html = "<html><body></body></html>"
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = [SEARCH_HTML, empty_html]
        scraper._http = mock_http

        result = scraper.scrape(query="test", max_pages=2)

        calls = mock_http.get_html.call_args_list
        assert len(calls) == 2
        # Second page should have start=51
        assert "start=51" in calls[1][0][0]
        scraper.close()

    def test_search_stops_on_empty_results(self):
        empty_html = "<html><body></body></html>"
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = empty_html
        scraper._http = mock_http

        result = scraper.scrape(query="xyznoexist", max_pages=3)

        assert len(result.data) == 0
        assert mock_http.get_html.call_count == 1
        scraper.close()

    def test_search_error_handling(self):
        scraper = IMDBScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = Exception("network error")
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        assert "network error" in result.errors[0].message
        scraper.close()


class TestIMDBScraperParseChartItem:
    def test_returns_none_without_title(self):
        scraper = IMDBScraper()
        soup = BeautifulSoup(
            '<li class="ipc-metadata-list-summary-item"><span>no title</span></li>',
            "lxml",
        )
        item = soup.select_one("li")
        result = scraper._parse_chart_item(item)
        assert result is None
