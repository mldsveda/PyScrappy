"""YouTube channel and search scraper."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult


class YouTubeScraper(BaseScraper):
    """Scrape YouTube search results and channel videos.

    Uses the initial page data embedded in YouTube's HTML (no API key needed).
    For channels with many videos, use the ``render_js=True`` option with
    ``scroll_pages`` to load more content.

    Usage::

        with YouTubeScraper() as scraper:
            # Search
            result = scraper.scrape(query="python tutorial", max_results=20)

            # Channel videos (requires browser for full results)
            result = scraper.scrape(
                channel_url="https://www.youtube.com/@3blue1brown/videos",
                render_js=True,
                scroll_pages=3,
            )
    """

    name = "youtube"

    def scrape(  # type: ignore[override]
        self,
        query: str | None = None,
        channel_url: str | None = None,
        max_results: int = 20,
        render_js: bool = False,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Scrape YouTube videos.

        Args:
            query: Search query string.
            channel_url: Full URL to a YouTube channel's videos page.
            max_results: Maximum number of videos to return.
            render_js: Use browser for JS rendering (needed for full channel scraping).
            scroll_pages: Number of scroll-downs for infinite scroll (with render_js).

        Returns:
            ScrapeResult with video data (title, url, views, published, channel, duration).
        """
        if channel_url:
            return self._scrape_channel(channel_url, max_results, render_js, scroll_pages)
        if query:
            return self._scrape_search(query, max_results, render_js)
        raise ValueError("Provide either query or channel_url")

    async def scrape_async(  # type: ignore[override]
        self,
        query: str | None = None,
        channel_url: str | None = None,
        max_results: int = 20,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape`.

        The async path uses plain HTTP and does not support JavaScript rendering
        or scrolling. Use :meth:`scrape` with ``render_js=True`` and
        ``scroll_pages`` for JS-rendered channel pages.
        """
        if channel_url:
            return await self._scrape_channel_async(channel_url, max_results)
        if query:
            return await self._scrape_search_async(query, max_results)
        raise ValueError("Provide either query or channel_url")

    def _scrape_search(self, query: str, max_results: int, render_js: bool) -> ScrapeResult:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        html = self.fetch_html(url, render_js=render_js)
        videos = self._extract_from_html(html, max_results)

        return ScrapeResult(
            data=videos,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    async def _scrape_search_async(self, query: str, max_results: int) -> ScrapeResult:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        html = await self.fetch_html_async(url)
        videos = self._extract_from_html(html, max_results)

        return ScrapeResult(
            data=videos,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _scrape_channel(
        self, channel_url: str, max_results: int, render_js: bool, scroll_pages: int
    ) -> ScrapeResult:
        if render_js:
            html = self.browser.get_html(
                channel_url,
                wait_for="networkidle",
                scroll_pages=scroll_pages,
            )
        else:
            html = self.http.get_html(channel_url)

        videos = self._extract_from_html(html, max_results)

        return ScrapeResult(
            data=videos,
            metadata=ScrapeMetadata(source_urls=[channel_url], scraper=self.name),
        )

    async def _scrape_channel_async(self, channel_url: str, max_results: int) -> ScrapeResult:
        html = await self.async_http.get_html(channel_url)
        videos = self._extract_from_html(html, max_results)

        return ScrapeResult(
            data=videos,
            metadata=ScrapeMetadata(source_urls=[channel_url], scraper=self.name),
        )

    def _extract_from_html(self, html: str, max_results: int) -> list[dict[str, Any]]:
        """Extract video data from YouTube's embedded JSON (ytInitialData)."""
        videos: list[dict[str, Any]] = []

        # YouTube embeds data as ytInitialData in the page HTML
        match = re.search(r"var ytInitialData\s*=\s*({.*?});</script>", html, re.DOTALL)
        if not match:
            # Try alternate pattern
            match = re.search(r"ytInitialData\s*=\s*'(.*?)'", html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1).encode().decode("unicode_escape"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return videos
            else:
                # Fall back to BS4 parsing of rendered HTML
                return self._extract_from_rendered_html(html, max_results)
        else:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                return videos

        # Walk the nested JSON to find video renderers
        renderers = self._find_video_renderers(data)

        for renderer in renderers[:max_results]:
            video = self._parse_renderer(renderer)
            if video and video.get("title"):
                videos.append(video)

        return videos

    def _find_video_renderers(self, data: Any) -> list[dict[str, Any]]:
        """Recursively find all videoRenderer objects in ytInitialData."""
        renderers: list[dict[str, Any]] = []

        if isinstance(data, dict):
            if "videoRenderer" in data:
                renderers.append(data["videoRenderer"])
            for value in data.values():
                renderers.extend(self._find_video_renderers(value))
        elif isinstance(data, list):
            for item in data:
                renderers.extend(self._find_video_renderers(item))

        return renderers

    def _parse_renderer(self, renderer: dict[str, Any]) -> dict[str, Any]:
        """Parse a videoRenderer JSON object into a flat dict."""
        video: dict[str, Any] = {}

        # Title
        title_runs = renderer.get("title", {}).get("runs", [])
        if title_runs:
            video["title"] = title_runs[0].get("text", "")

        # URL
        video_id = renderer.get("videoId", "")
        if video_id:
            video["url"] = f"https://www.youtube.com/watch?v={video_id}"

        # Channel name
        channel_runs = renderer.get("ownerText", {}).get("runs", [])
        if channel_runs:
            video["channel"] = channel_runs[0].get("text", "")

        # View count
        view_text = renderer.get("viewCountText", {}).get("simpleText", "")
        if not view_text:
            view_runs = renderer.get("viewCountText", {}).get("runs", [])
            if view_runs:
                view_text = "".join(r.get("text", "") for r in view_runs)
        video["views"] = view_text

        # Published time
        video["published"] = renderer.get("publishedTimeText", {}).get("simpleText", "")

        # Duration
        video["duration"] = (
            renderer.get("lengthText", {}).get("simpleText", "")
            or renderer.get("thumbnailOverlays", [{}])[0]
            .get("thumbnailOverlayTimeStatusRenderer", {})
            .get("text", {})
            .get("simpleText", "")
            if renderer.get("thumbnailOverlays")
            else ""
        )

        # Thumbnail
        thumbs = renderer.get("thumbnail", {}).get("thumbnails", [])
        if thumbs:
            video["thumbnail"] = thumbs[-1].get("url", "")

        return video

    def _extract_from_rendered_html(self, html: str, max_results: int) -> list[dict[str, Any]]:
        """Fallback: parse rendered HTML with BeautifulSoup."""
        soup = self.parse_html(html)
        videos: list[dict[str, Any]] = []

        for item in soup.select("a#video-title, a.yt-simple-endpoint[href*='watch']"):
            title = item.get("title") or item.get_text(strip=True)
            href = str(item.get("href", ""))
            if not href or not title:
                continue

            if href.startswith("/"):
                href = "https://www.youtube.com" + href

            videos.append({"title": title, "url": href})

            if len(videos) >= max_results:
                break

        return videos
