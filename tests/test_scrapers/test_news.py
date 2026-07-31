"""Tests for pyscrappy.scrapers.news."""

from unittest.mock import MagicMock

import pytest

from pyscrappy.scrapers.news import NewsScraper

RSS_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Test Feed</title>
    <item>
        <title>Article One</title>
        <link>https://example.com/article1</link>
        <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
        <description>&lt;p&gt;Summary of article one.&lt;/p&gt;</description>
    </item>
    <item>
        <title>Article Two</title>
        <link>https://example.com/article2</link>
        <pubDate>Tue, 02 Jan 2024 00:00:00 GMT</pubDate>
        <description>Summary of article two.</description>
    </item>
</channel>
</rss>
"""

ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Atom Feed</title>
    <entry>
        <title>Atom Article</title>
        <link href="https://example.com/atom1"/>
        <updated>2024-01-01T00:00:00Z</updated>
        <summary>Atom summary text here.</summary>
    </entry>
</feed>
"""

ARTICLE_HTML = """
<html>
<head>
    <title>Full Article Title</title>
    <meta property="og:title" content="OG Article Title">
    <meta property="article:published_time" content="2024-01-15T10:00:00Z">
    <meta name="author" content="Jane Doe">
</head>
<body>
<article>
    <p>This is the first paragraph of the article with enough text to pass the filter threshold easily.</p>
    <p>This is the second paragraph of the article with enough text to pass the filter threshold as well.</p>
    <p>Short</p>
</article>
</body>
</html>
"""

SITE_WITH_RSS = """
<html>
<head>
    <link type="application/rss+xml" href="/feed.xml">
</head>
<body><p>Main page</p></body>
</html>
"""

SITE_WITHOUT_RSS = """
<html>
<head></head>
<body>
    <a href="/2024/01/article-slug">Long Headline About Important News Event Today</a>
    <a href="/about">About</a>
    <a href="/story/breaking-news">Another Breaking News Story That Has a Long Title</a>
</body>
</html>
"""


class TestNewsScraperInit:
    def test_name(self):
        scraper = NewsScraper()
        assert scraper.name == "news"


class TestNewsScraperValidation:
    def test_no_args_raises(self):
        scraper = NewsScraper()
        with pytest.raises(ValueError, match="Provide at least one"):
            scraper.scrape()


class TestNewsScraperFeed:
    def test_parse_rss_feed(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = RSS_FEED
        scraper._http = mock_http

        result = scraper.scrape(feed_url="https://example.com/rss")

        assert len(result.data) == 2
        assert result.data[0]["title"] == "Article One"
        assert result.data[0]["link"] == "https://example.com/article1"
        assert result.data[0]["published"] == "Mon, 01 Jan 2024 00:00:00 GMT"
        assert result.data[0]["summary"] == "Summary of article one."  # HTML stripped
        scraper.close()

    def test_parse_atom_feed(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = ATOM_FEED
        scraper._http = mock_http

        result = scraper.scrape(feed_url="https://example.com/atom")

        assert len(result.data) == 1
        assert result.data[0]["title"] == "Atom Article"
        assert result.data[0]["link"] == "https://example.com/atom1"
        scraper.close()

    def test_max_articles_limit(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = RSS_FEED
        scraper._http = mock_http

        result = scraper.scrape(feed_url="https://example.com/rss", max_articles=1)
        assert len(result.data) == 1
        scraper.close()

    def test_invalid_xml(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "not valid xml <<<"
        scraper._http = mock_http

        result = scraper.scrape(feed_url="https://example.com/bad")
        assert result.data == []
        scraper.close()


class TestNewsScraperArticle:
    def test_scrape_article(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = ARTICLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(article_url="https://example.com/article/1")

        assert len(result.data) == 1
        article = result.data[0]
        assert article["title"] == "OG Article Title"  # og:title overrides <title>
        assert article["published"] == "2024-01-15T10:00:00Z"
        assert article["author"] == "Jane Doe"
        assert "first paragraph" in article["text"]
        assert article["word_count"] > 0
        assert article["url"] == "https://example.com/article/1"
        scraper.close()

    def test_article_filters_short_paragraphs(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = ARTICLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(article_url="https://example.com/article/1")
        # "Short" paragraph should be filtered out
        assert "Short" not in result.data[0]["text"]
        scraper.close()


class TestNewsScraperSite:
    def test_auto_discovers_rss(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = [SITE_WITH_RSS, RSS_FEED]
        scraper._http = mock_http

        result = scraper.scrape(site_url="https://example.com")

        assert len(result.data) == 2  # articles from RSS feed
        scraper.close()

    def test_fallback_to_article_links(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SITE_WITHOUT_RSS
        scraper._http = mock_http

        result = scraper.scrape(site_url="https://example.com")

        # Should extract links that look like articles
        assert len(result.data) >= 1
        links = [d["link"] for d in result.data]
        assert any("/2024/" in link for link in links)
        scraper.close()

    def test_no_feed_or_articles_adds_error(self):
        scraper = NewsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body><p>Nothing here</p></body></html>"
        scraper._http = mock_http

        result = scraper.scrape(site_url="https://example.com")
        assert len(result.errors) == 1
        assert "No RSS feed or article links found" in result.errors[0].message
        scraper.close()


class TestNewsScraperHelpers:
    def test_clean_html_strips_tags(self):
        assert NewsScraper._clean_html("<p>Hello <b>World</b></p>") == "Hello World"
        assert NewsScraper._clean_html("No tags") == "No tags"
        assert NewsScraper._clean_html("") == ""

    def test_xml_text_missing_element(self):
        from xml.etree import ElementTree

        root = ElementTree.fromstring("<item><title>Test</title></item>")
        assert NewsScraper._xml_text(root, "title") == "Test"
        assert NewsScraper._xml_text(root, "description") == ""
