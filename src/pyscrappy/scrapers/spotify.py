"""Spotify scraper — search tracks, artists, and playlists.

.. note::

    Spotify's web player is heavily JS-rendered. This scraper
    works best with ``render_js=True``. For production use,
    consider the official Spotify Web API.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class SpotifyScraper(BaseScraper):
    """Scrape track and playlist data from Spotify.

    Usage::

        with SpotifyScraper() as scraper:
            # Search tracks
            result = scraper.scrape(query="Daft Punk", search_type="tracks")

            # Scrape a public playlist (requires browser)
            result = scraper.scrape(
                playlist_url="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
                render_js=True,
            )
    """

    name = "spotify"

    def scrape(  # type: ignore[override]
        self,
        query: str | None = None,
        search_type: str = "tracks",
        playlist_url: str | None = None,
        max_results: int = 20,
        render_js: bool = False,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Scrape Spotify data.

        Args:
            query: Search query string.
            search_type: Type of search — ``"tracks"``, ``"artists"``, ``"albums"``,
                or ``"playlists"``.
            playlist_url: Direct URL to a public Spotify playlist.
            max_results: Maximum number of results.
            render_js: Use browser for JS rendering.
            scroll_pages: Number of scrolls for loading more content.

        Returns:
            ScrapeResult with track/artist/playlist data.
        """
        if playlist_url:
            return self._scrape_playlist(playlist_url, max_results, render_js, scroll_pages)
        if query:
            return self._scrape_search(query, search_type, max_results, render_js)
        raise ValueError("Provide either query or playlist_url")

    def _scrape_search(
        self, query: str, search_type: str, max_results: int, render_js: bool
    ) -> ScrapeResult:
        url = f"https://open.spotify.com/search/{quote_plus(query)}/{search_type}"
        errors: list[ScrapeError] = []

        if render_js:
            html = self.browser.get_html(url, wait_for="networkidle")
        else:
            html = self.http.get_html(url)

        items = self._extract_items(html, max_results)

        if not items:
            errors.append(
                ScrapeError(
                    url=url,
                    message="No results extracted. Spotify requires JS rendering — use render_js=True.",
                )
            )

        return ScrapeResult(
            data=items,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _scrape_playlist(
        self, url: str, max_results: int, render_js: bool, scroll_pages: int
    ) -> ScrapeResult:
        errors: list[ScrapeError] = []

        if render_js:
            html = self.browser.get_html(url, wait_for="networkidle", scroll_pages=scroll_pages)
        else:
            html = self.http.get_html(url)

        tracks = self._extract_playlist_tracks(html, max_results)

        if not tracks:
            errors.append(
                ScrapeError(
                    url=url,
                    message="No tracks extracted. Use render_js=True for playlists.",
                )
            )

        return ScrapeResult(
            data=tracks,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _extract_items(self, html: str, max_results: int) -> list[dict[str, Any]]:
        """Extract search results from Spotify page."""
        items: list[dict[str, Any]] = []

        # Try embedded JSON data
        json_items = self._extract_from_resource(html, max_results)
        if json_items:
            return json_items

        # Fallback: parse rendered HTML
        soup = self.parse_html(html)

        for card in soup.select(
            "[data-testid='tracklist-row'], [data-testid='search-result-item'], div[role='row']"
        ):
            item: dict[str, Any] = {}

            # Title
            title_el = card.select_one(
                "a[data-testid='internal-track-link'] div, div[class*='Type__TypeElement'] a"
            )
            if title_el:
                item["title"] = title_el.get_text(strip=True)

            # Artist
            artist_el = card.select_one("span[data-testid='artists-names'], a[href*='/artist/']")
            if artist_el:
                item["artist"] = artist_el.get_text(strip=True)

            # Duration
            duration_el = card.select_one(
                "[data-testid='tracklist-duration'], div[class*='Duration']"
            )
            if duration_el:
                item["duration"] = duration_el.get_text(strip=True)

            # Link
            link = card.select_one("a[href*='/track/'], a[href*='/artist/'], a[href*='/album/']")
            if link:
                item["url"] = "https://open.spotify.com" + str(link.get("href", ""))

            if item.get("title"):
                items.append(item)

            if len(items) >= max_results:
                break

        return items

    def _extract_playlist_tracks(self, html: str, max_results: int) -> list[dict[str, Any]]:
        """Extract tracks from a playlist page."""
        # Try resource data first
        tracks = self._extract_from_resource(html, max_results)
        if tracks:
            return tracks

        # Fallback to generic extraction
        return self._extract_items(html, max_results)

    def _extract_from_resource(self, html: str, max_results: int) -> list[dict[str, Any]]:
        """Extract data from Spotify's embedded resource JSON."""
        items: list[dict[str, Any]] = []

        match = re.search(
            r'<script id="initial-state" type="text/plain">(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not match:
            return items

        try:
            import base64

            decoded = base64.b64decode(match.group(1))
            data = json.loads(decoded)
        except Exception:
            return items

        # Walk through to find track objects
        tracks = self._find_tracks(data)
        for track in tracks[:max_results]:
            items.append(track)

        return items

    def _find_tracks(self, data: Any) -> list[dict[str, Any]]:
        """Recursively find track data in Spotify's JSON."""
        tracks: list[dict[str, Any]] = []

        if isinstance(data, dict):
            if data.get("type") == "track" and data.get("name"):
                artists = data.get("artists", [])
                tracks.append(
                    {
                        "title": data.get("name", ""),
                        "artist": ", ".join(a.get("name", "") for a in artists) if artists else "",
                        "album": data.get("album", {}).get("name", ""),
                        "duration_ms": data.get("duration_ms"),
                        "url": f"https://open.spotify.com/track/{data.get('id', '')}",
                    }
                )
            for value in data.values():
                tracks.extend(self._find_tracks(value))
        elif isinstance(data, list):
            for item in data:
                tracks.extend(self._find_tracks(item))

        return tracks
