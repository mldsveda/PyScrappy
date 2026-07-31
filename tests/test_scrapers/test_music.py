"""Tests for music scrapers: SoundCloud, Spotify."""

import json
from unittest.mock import MagicMock

import pytest

from pyscrappy.scrapers.soundcloud import SoundCloudScraper
from pyscrappy.scrapers.spotify import SpotifyScraper

# --- SoundCloud ---

SC_HYDRATION = [
    {
        "data": {
            "collection": [
                {
                    "kind": "track",
                    "title": "Lo-Fi Beats Vol.1",
                    "user": {"username": "ChillBeats"},
                    "permalink_url": "https://soundcloud.com/chillbeats/lofi-vol1",
                    "playback_count": 500000,
                    "likes_count": 10000,
                    "duration": 180000,
                    "genre": "Lo-Fi",
                    "created_at": "2024-01-01T00:00:00Z",
                },
                {
                    "kind": "playlist",
                    "title": "Not a Track",
                },
                {
                    "kind": "track",
                    "title": "Rainy Day Mix",
                    "user": {"username": "RainSounds"},
                    "permalink_url": "https://soundcloud.com/rainsounds/rainy-day",
                    "playback_count": 100000,
                    "likes_count": 3000,
                    "duration": 240000,
                    "genre": "Ambient",
                    "created_at": "2024-02-01T00:00:00Z",
                },
            ]
        }
    }
]

SC_HTML_WITH_HYDRATION = (
    "<html><body><script>window.__sc_hydration = "
    + json.dumps(SC_HYDRATION)
    + "; </script></body></html>"
)

SC_HTML_RENDERED = """
<html><body>
<li class="searchList__item">
    <a href="/artist/track-name"><span class="sc-truncate">Track Title</span></a>
    <a href="/artist"><span class="soundTitle__usernameText">Artist Name</span></a>
    <span class="sc-ministats-plays"><span aria-hidden="true">1.2M</span></span>
</li>
</body></html>
"""


class TestSoundCloudScraper:
    def test_name(self):
        assert SoundCloudScraper().name == "soundcloud"

    def test_extract_from_hydration(self):
        scraper = SoundCloudScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SC_HTML_WITH_HYDRATION
        scraper._http = mock_http

        result = scraper.scrape(query="lo-fi beats")

        # Should skip the playlist, only include tracks
        assert len(result.data) == 2
        assert result.data[0]["title"] == "Lo-Fi Beats Vol.1"
        assert result.data[0]["artist"] == "ChillBeats"
        assert result.data[0]["plays"] == 500000
        assert result.data[0]["likes"] == 10000
        assert result.data[0]["duration_ms"] == 180000
        assert result.data[0]["genre"] == "Lo-Fi"
        scraper.close()

    def test_max_results_limit(self):
        scraper = SoundCloudScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SC_HTML_WITH_HYDRATION
        scraper._http = mock_http

        result = scraper.scrape(query="lo-fi", max_results=1)
        assert len(result.data) == 1
        scraper.close()

    def test_html_fallback(self):
        scraper = SoundCloudScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SC_HTML_RENDERED
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.data) == 1
        assert result.data[0]["title"] == "Track Title"
        scraper.close()

    def test_no_tracks_adds_error(self):
        scraper = SoundCloudScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        assert "No tracks extracted" in result.errors[0].message
        scraper.close()

    def test_search_url(self):
        scraper = SoundCloudScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(query="lo fi beats")
        url = mock_http.get_html.call_args[0][0]
        assert "soundcloud.com/search/sounds" in url
        assert "q=lo+fi+beats" in url
        scraper.close()


# --- Spotify ---

SPOTIFY_RESOURCE_DATA = {
    "entities": {
        "items": {
            "track1": {
                "type": "track",
                "name": "Get Lucky",
                "artists": [{"name": "Daft Punk"}, {"name": "Pharrell Williams"}],
                "album": {"name": "Random Access Memories"},
                "duration_ms": 369000,
                "id": "2Foc5Q5nqNiosCNqttzHof",
            }
        }
    }
}

SPOTIFY_HTML_WITH_RESOURCE = (
    "<html><body>"
    '<script id="initial-state" type="text/plain">'
    + __import__("base64").b64encode(json.dumps(SPOTIFY_RESOURCE_DATA).encode()).decode()
    + "</script></body></html>"
)

SPOTIFY_HTML_RENDERED = """
<html><body>
<div data-testid="tracklist-row">
    <a data-testid="internal-track-link"><div>Song Title</div></a>
    <span data-testid="artists-names">Artist Name</span>
    <div data-testid="tracklist-duration">3:45</div>
    <a href="/track/abc123">Link</a>
</div>
</body></html>
"""


class TestSpotifyScraper:
    def test_name(self):
        assert SpotifyScraper().name == "spotify"

    def test_no_args_raises(self):
        scraper = SpotifyScraper()
        with pytest.raises(ValueError, match="Provide either query or playlist_url"):
            scraper.scrape()

    def test_extract_from_resource(self):
        scraper = SpotifyScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SPOTIFY_HTML_WITH_RESOURCE
        scraper._http = mock_http

        result = scraper.scrape(query="Daft Punk")

        assert len(result.data) == 1
        assert result.data[0]["title"] == "Get Lucky"
        assert result.data[0]["artist"] == "Daft Punk, Pharrell Williams"
        assert result.data[0]["album"] == "Random Access Memories"
        assert result.data[0]["duration_ms"] == 369000
        scraper.close()

    def test_html_fallback(self):
        scraper = SpotifyScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SPOTIFY_HTML_RENDERED
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.data) == 1
        assert result.data[0]["title"] == "Song Title"
        assert result.data[0]["artist"] == "Artist Name"
        assert result.data[0]["duration"] == "3:45"
        scraper.close()

    def test_no_results_adds_error(self):
        scraper = SpotifyScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        assert "No results extracted" in result.errors[0].message
        scraper.close()

    def test_playlist_scrape(self):
        scraper = SpotifyScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = SPOTIFY_HTML_WITH_RESOURCE
        scraper._http = mock_http

        result = scraper.scrape(
            playlist_url="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        )
        assert len(result.data) == 1
        scraper.close()

    def test_search_url(self):
        scraper = SpotifyScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(query="Daft Punk", search_type="artists")
        url = mock_http.get_html.call_args[0][0]
        assert "open.spotify.com/search/Daft+Punk/artists" in url
        scraper.close()
