"""Tests for remaining scrapers: LinkedIn, ImageSearch."""

from unittest.mock import MagicMock

import pytest

from pyscrappy.scrapers.image_search import ImageSearchScraper
from pyscrappy.scrapers.linkedin import LinkedInJobsScraper

# --- LinkedIn ---

LINKEDIN_HTML = """
<html><body>
<div class="base-card">
    <span class="base-search-card__title">Senior Python Developer</span>
    <a class="base-search-card__subtitle" href="#">Google</a>
    <span class="job-search-card__location">Mountain View, CA</span>
    <a class="base-card__full-link" href="https://linkedin.com/jobs/view/12345?trk=abc">Link</a>
    <time datetime="2024-01-15">2 days ago</time>
    <span class="job-search-card__salary-info">$180K - $250K</span>
</div>
</body></html>
"""

LINKEDIN_AUTH_WALL = """
<html><body>
<form class="login__form">
    <input type="email" name="session_key">
</form>
</body></html>
"""


class TestLinkedInJobsScraper:
    def test_name(self):
        assert LinkedInJobsScraper().name == "linkedin"

    def test_parse_job_cards(self):
        scraper = LinkedInJobsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = LINKEDIN_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="python developer")

        assert len(result.data) == 1
        job = result.data[0]
        assert job["title"] == "Senior Python Developer"
        assert job["company"] == "Google"
        assert job["location"] == "Mountain View, CA"
        assert job["posted"] == "2024-01-15"
        assert job["salary"] == "$180K - $250K"
        assert "12345" in job["url"]
        # URL should be cleaned (no query params)
        assert "?" not in job["url"]
        scraper.close()

    def test_auth_wall_detection(self):
        scraper = LinkedInJobsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = LINKEDIN_AUTH_WALL
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        assert "authentication" in result.errors[0].message.lower()
        scraper.close()

    def test_pagination_offset(self):
        empty = "<html><body></body></html>"
        scraper = LinkedInJobsScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = [LINKEDIN_HTML, empty]
        scraper._http = mock_http

        scraper.scrape(query="test", max_pages=2)

        calls = mock_http.get_html.call_args_list
        assert "start=0" in calls[0][0][0]
        assert "start=25" in calls[1][0][0]
        scraper.close()

    def test_url_with_location(self):
        scraper = LinkedInJobsScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(query="developer", location="San Francisco")
        url = mock_http.get_html.call_args[0][0]
        assert "keywords=developer" in url
        assert "location=San+Francisco" in url
        scraper.close()

    def test_fetch_error(self):
        scraper = LinkedInJobsScraper()
        mock_http = MagicMock()
        mock_http.get_html.side_effect = Exception("rate limited")
        scraper._http = mock_http

        result = scraper.scrape(query="test")
        assert len(result.errors) == 1
        scraper.close()


# --- ImageSearch ---

BING_HTML = """
<html><body>
<a class="iusc" m='{"murl":"https://img.com/photo.jpg","turl":"https://thumb.com/t.jpg","t":"A Photo","purl":"https://source.com","mw":1920,"mh":1080}'>
    <img src="https://thumb.com/t.jpg">
</a>
<a class="iusc" m='{"murl":"https://img.com/photo2.png","turl":"https://thumb.com/t2.jpg","t":"Photo 2","purl":"https://source2.com","mw":800,"mh":600}'>
    <img src="https://thumb.com/t2.jpg">
</a>
</body></html>
"""

GOOGLE_HTML = """
<html><body>
<img src="https://www.google.com/images/branding/googlelogo.png" alt="Google">
<img src="https://images.example.com/photo1.jpg" alt="Result 1">
<img src="https://images.example.com/photo2.jpg" alt="Result 2">
</body></html>
"""


class TestImageSearchScraper:
    def test_name(self):
        assert ImageSearchScraper().name == "image_search"

    def test_bing_search(self):
        scraper = ImageSearchScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = BING_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="golden retriever", engine="bing")

        assert len(result.data) == 2
        assert result.data[0]["url"] == "https://img.com/photo.jpg"
        assert result.data[0]["thumbnail"] == "https://thumb.com/t.jpg"
        assert result.data[0]["title"] == "A Photo"
        assert result.data[0]["width"] == 1920
        assert result.data[0]["height"] == 1080
        scraper.close()

    def test_google_search(self):
        scraper = ImageSearchScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = GOOGLE_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="sunset", engine="google")

        # Should skip the Google logo
        assert len(result.data) == 2
        assert all("example.com" in d["url"] for d in result.data)
        scraper.close()

    def test_both_engines_return_the_same_key_set(self):
        """Every engine emits the canonical schema, so callers can rely on the
        same keys regardless of engine (the Google path just leaves some empty)."""
        expected = {"url", "thumbnail", "title", "source_page", "width", "height"}

        bing = ImageSearchScraper()
        bing._http = MagicMock()
        bing._http.get_html.return_value = BING_HTML
        bing_result = bing.scrape(query="q", engine="bing")
        bing.close()

        google = ImageSearchScraper()
        google._http = MagicMock()
        google._http.get_html.return_value = GOOGLE_HTML
        google_result = google.scrape(query="q", engine="google")
        google.close()

        assert bing_result.data and google_result.data
        for item in bing_result.data + google_result.data:
            assert set(item.keys()) == expected

        # the Google path can't populate every field, but the keys still exist
        g = google_result.data[0]
        assert g["url"] and g["thumbnail"] == "" and g["width"] is None

    def test_max_images_limit(self):
        scraper = ImageSearchScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = BING_HTML
        scraper._http = mock_http

        result = scraper.scrape(query="test", max_images=1)
        assert len(result.data) == 1
        scraper.close()

    def test_guess_extension(self):
        assert ImageSearchScraper._guess_extension("https://img.com/photo.jpg") == ".jpg"
        assert ImageSearchScraper._guess_extension("https://img.com/pic.png") == ".png"
        assert ImageSearchScraper._guess_extension("https://img.com/anim.gif") == ".gif"
        assert ImageSearchScraper._guess_extension("https://img.com/pic.webp") == ".webp"
        assert ImageSearchScraper._guess_extension("https://img.com/unknown") == ".jpg"

    def test_bing_fallback_to_img_tags(self):
        html = """
        <html><body>
        <img src="https://external.com/real-image.jpg" alt="Image">
        <img src="https://www.bing.com/th?id=OIP.xxx" alt="Bing thumb">
        </body></html>
        """
        scraper = ImageSearchScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = html
        scraper._http = mock_http

        result = scraper.scrape(query="test", engine="bing")
        # Should only include the external image, not the bing thumbnail
        assert len(result.data) == 1
        assert "external.com" in result.data[0]["url"]
        scraper.close()

    def test_download_images(self, tmp_path):
        scraper = ImageSearchScraper()
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.content = b"\x89PNG\r\n\x1a\n"
        mock_http.get.return_value = mock_response
        scraper._http = mock_http

        images = [{"url": "https://img.com/photo.png"}]
        directory = str(tmp_path / "downloads")
        scraper._download_images(images, directory)

        assert images[0]["local_path"].endswith(".png")
        assert "image_0001" in images[0]["local_path"]
        scraper.close()

    def test_default_engine_is_bing(self):
        scraper = ImageSearchScraper()
        mock_http = MagicMock()
        mock_http.get_html.return_value = "<html><body></body></html>"
        scraper._http = mock_http

        scraper.scrape(query="test")
        url = mock_http.get_html.call_args[0][0]
        assert "bing.com" in url
        scraper.close()

    def test_unsupported_engine_raises_value_error(self):
        scraper = ImageSearchScraper()
        with pytest.raises(ValueError, match="Unsupported engine 'googel'"):
            scraper.scrape(query="test", engine="googel")

    @pytest.mark.anyio
    async def test_unsupported_engine_raises_value_error_async(self):
        scraper = ImageSearchScraper()
        with pytest.raises(ValueError, match="Unsupported engine 'googel'"):
            await scraper.scrape_async(query="test", engine="googel")
