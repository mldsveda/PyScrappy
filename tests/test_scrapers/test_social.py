"""Tests for social media scrapers: YouTube, Instagram, Twitter."""

import json
from unittest.mock import MagicMock

import pytest

from pyscrappy.scrapers.youtube import YouTubeScraper
from pyscrappy.scrapers.instagram import InstagramScraper
from pyscrappy.scrapers.twitter import TwitterScraper


# --- YouTube ---

YT_INITIAL_DATA = {
    "contents": {
        "twoColumnSearchResultsRenderer": {
            "primaryContents": {
                "sectionListRenderer": {
                    "contents": [{
                        "itemSectionRenderer": {
                            "contents": [{
                                "videoRenderer": {
                                    "videoId": "dQw4w9WgXcQ",
                                    "title": {"runs": [{"text": "Python Tutorial"}]},
                                    "ownerText": {"runs": [{"text": "Corey Schafer"}]},
                                    "viewCountText": {"simpleText": "5M views"},
                                    "publishedTimeText": {"simpleText": "2 years ago"},
                                    "lengthText": {"simpleText": "45:23"},
                                    "thumbnailOverlays": [{}],
                                    "thumbnail": {"thumbnails": [
                                        {"url": "https://i.ytimg.com/vi/x/default.jpg"},
                                        {"url": "https://i.ytimg.com/vi/x/hqdefault.jpg"},
                                    ]},
                                }
                            }]
                        }
                    }]
                }
            }
        }
    }
}

YT_HTML = (
    '<html><body><script>var ytInitialData = '
    + json.dumps(YT_INITIAL_DATA)
    + ';</script></body></html>'
)

YT_RENDERED_HTML = """
<html><body>
<a id="video-title" title="Rendered Video" href="/watch?v=abc123">Rendered Video</a>
</body></html>
"""


class TestYouTubeScraper:
    def test_name(self):
        assert YouTubeScraper().name == "youtube"

    def test_no_args_raises(self):
        scraper = YouTubeScraper()
        with pytest.raises(ValueError, match="Provide either query or channel_url"):
            scraper.scrape()

    def test_search_from_json(self):
        scraper = YouTubeScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = YT_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="python tutorial")

        assert len(result.data) == 1
        assert result.data[0]["title"] == "Python Tutorial"
        assert result.data[0]["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert result.data[0]["channel"] == "Corey Schafer"
        assert result.data[0]["views"] == "5M views"
        assert result.data[0]["duration"] == "45:23"
        assert result.data[0]["thumbnail"] == "https://i.ytimg.com/vi/x/hqdefault.jpg"
        scraper.close()

    def test_fallback_to_rendered_html(self):
        scraper = YouTubeScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = YT_RENDERED_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="test")

        assert len(result.data) == 1
        assert result.data[0]["title"] == "Rendered Video"
        assert "abc123" in result.data[0]["url"]
        scraper.close()

    def test_max_results_limit(self):
        scraper = YouTubeScraper()
        # Build HTML with multiple videos
        data = {"contents": [{"videoRenderer": {
            "videoId": f"vid{i}",
            "title": {"runs": [{"text": f"Video {i}"}]},
        }} for i in range(10)]}
        html = f'<html><body><script>var ytInitialData = {json.dumps(data)};</script></body></html>'
        mock_http = MagicMock()
        mock_http.get_html.return_value = html
        scraper._http = mock_http

        result = scraper.scrape(query="test", max_results=3)
        assert len(result.data) <= 3
        scraper.close()

    def test_search_url(self):
        scraper = YouTubeScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(query="python tutorial")
        url = mock_http.get_html.call_args[0][0]
        assert "youtube.com/results" in url
        assert "search_query=python+tutorial" in url
        scraper.close()


# --- Instagram ---

IG_SHARED_DATA = {
    "entry_data": {
        "ProfilePage": [{
            "graphql": {
                "user": {
                    "full_name": "National Geographic",
                    "biography": "Experience the world.",
                    "edge_followed_by": {"count": 250000000},
                    "edge_follow": {"count": 150},
                    "edge_owner_to_timeline_media": {
                        "count": 25000,
                        "edges": [{
                            "node": {
                                "shortcode": "ABC123",
                                "edge_media_to_caption": {"edges": [{"node": {"text": "Beautiful sunset"}}]},
                                "edge_liked_by": {"count": 100000},
                                "edge_media_to_comment": {"count": 500},
                            }
                        }],
                    },
                    "is_verified": True,
                    "profile_pic_url_hd": "https://pic.com/natgeo.jpg",
                    "external_url": "https://natgeo.com",
                }
            }
        }]
    }
}

IG_HTML_WITH_JSON = (
    '<html><body><script>window._sharedData = '
    + json.dumps(IG_SHARED_DATA)
    + ';</script></body></html>'
)

IG_HTML_FALLBACK = """
<html>
<head>
    <meta name="description" content="250M Followers, 150 Following - National Geographic">
    <meta property="og:title" content="National Geographic (@natgeo)">
</head>
<body></body>
</html>
"""

IG_HASHTAG_DATA = {
    "entry_data": {
        "TagPage": [{
            "graphql": {
                "hashtag": {
                    "edge_hashtag_to_media": {
                        "edges": [{
                            "node": {
                                "shortcode": "XYZ789",
                                "edge_media_to_caption": {"edges": [{"node": {"text": "Sunset pic"}}]},
                                "edge_liked_by": {"count": 5000},
                                "edge_media_to_comment": {"count": 50},
                                "is_video": False,
                            }
                        }]
                    }
                }
            }
        }]
    }
}

IG_HASHTAG_HTML = (
    '<html><body><script>window._sharedData = '
    + json.dumps(IG_HASHTAG_DATA)
    + ';</script></body></html>'
)


class TestInstagramScraper:
    def test_name(self):
        assert InstagramScraper().name == "instagram"

    def test_no_args_raises(self):
        scraper = InstagramScraper()
        with pytest.raises(ValueError, match="Provide either username or hashtag"):
            scraper.scrape()

    def test_profile_from_json(self):
        scraper = InstagramScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = IG_HTML_WITH_JSON
        scraper._http = mock_http

        result = scraper.scrape(username="natgeo")

        assert len(result.data) == 1
        profile = result.data[0]
        assert profile["username"] == "natgeo"
        assert profile["full_name"] == "National Geographic"
        assert profile["followers"] == 250000000
        assert profile["following"] == 150
        assert profile["is_verified"] is True
        assert len(profile["recent_posts"]) == 1
        assert profile["recent_posts"][0]["caption"] == "Beautiful sunset"
        scraper.close()

    def test_profile_html_fallback(self):
        scraper = InstagramScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = IG_HTML_FALLBACK
        scraper._http = mock_http

        result = scraper.scrape(username="natgeo")
        profile = result.data[0]
        assert profile["username"] == "natgeo"
        assert "National Geographic" in profile.get("full_name", "")
        scraper.close()

    def test_hashtag_from_json(self):
        scraper = InstagramScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = IG_HASHTAG_HTML
        scraper._http = mock_http

        result = scraper.scrape(hashtag="photography")

        assert len(result.data) == 1
        post = result.data[0]
        assert post["caption"] == "Sunset pic"
        assert post["likes"] == 5000
        assert post["is_video"] is False
        scraper.close()

    def test_hashtag_html_fallback(self):
        html = """
        <html><body>
        <a href="/p/ABC123/">Post 1</a>
        <a href="/p/DEF456/">Post 2</a>
        <a href="/p/ABC123/">Duplicate</a>
        </body></html>
        """
        scraper = InstagramScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = html
        scraper._http = mock_http

        result = scraper.scrape(hashtag="test")
        # Duplicates should be deduped
        assert len(result.data) == 2
        scraper.close()


# --- Twitter ---

TWITTER_RENDERED_HTML = """
<html><body>
<article data-testid="tweet">
    <a href="/user"><span>John Doe</span></a>
    <a href="/user"><span>@johndoe</span></a>
    <div data-testid="tweetText">This is a test tweet about Python</div>
    <time datetime="2024-01-15T10:00:00.000Z">Jan 15</time>
    <button data-testid="reply"><span>5</span></button>
    <button data-testid="retweet"><span>10</span></button>
    <button data-testid="like"><span>50</span></button>
</article>
</body></html>
"""

TWITTER_JSON_HTML = (
    '<html><body><script>window.__INITIAL_STATE__ = '
    + json.dumps({
        "entities": {
            "tweets": {
                "entities": {
                    "12345": {
                        "full_text": "JSON extracted tweet",
                        "created_at": "Mon Jan 15 10:00:00 +0000 2024",
                        "retweet_count": 20,
                        "favorite_count": 100,
                    }
                }
            }
        }
    })
    + ';</script></body></html>'
)


class TestTwitterScraper:
    def test_name(self):
        assert TwitterScraper().name == "twitter"

    def test_no_args_raises(self):
        scraper = TwitterScraper()
        with pytest.raises(ValueError, match="Provide either query or hashtag"):
            scraper.scrape()

    def test_hashtag_converted_to_query(self):
        scraper = TwitterScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        result = scraper.scrape(hashtag="python")
        url = mock_http.get_html.call_args[0][0]
        assert "%23python" in url  # #python URL-encoded
        scraper.close()

    def test_parse_rendered_html(self):
        scraper = TwitterScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = TWITTER_RENDERED_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="test")

        assert len(result.data) == 1
        tweet = result.data[0]
        assert tweet["text"] == "This is a test tweet about Python"
        assert tweet["name"] == "John Doe"
        assert tweet["handle"] == "@johndoe"
        assert tweet["timestamp"] == "2024-01-15T10:00:00.000Z"
        assert tweet["replies"] == "5"
        assert tweet["retweets"] == "10"
        assert tweet["likes"] == "50"
        scraper.close()

    def test_parse_from_json(self):
        scraper = TwitterScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = TWITTER_JSON_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="test")

        assert len(result.data) == 1
        assert result.data[0]["text"] == "JSON extracted tweet"
        assert result.data[0]["retweets"] == 20
        assert result.data[0]["likes"] == 100
        scraper.close()

    def test_no_tweets_adds_error(self):
        scraper = TwitterScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        assert "No tweets extracted" in result.errors[0].message
        scraper.close()
