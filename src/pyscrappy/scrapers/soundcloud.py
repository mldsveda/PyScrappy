"""SoundCloud scraper — search tracks and artists."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class SoundCloudScraper(BaseScraper):
    """Scrape tracks from SoundCloud.

    Usage::

        with SoundCloudScraper() as scraper:
            # Search tracks
            result = scraper.scrape(query="lo-fi beats", max_results=20)

            # With browser for more results
            result = scraper.scrape(
                query="lo-fi beats",
                render_js=True,
                scroll_pages=3,
            )
    """

    name = "soundcloud"

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_results: int = 20,
        render_js: bool = False,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Search for tracks on SoundCloud.

        Args:
            query: Search query string.
            max_results: Maximum number of tracks to return.
            render_js: Use browser for JS rendering.
            scroll_pages: Number of scrolls for loading more content.

        Returns:
            ScrapeResult with track data (title, artist, plays, duration, url).
        """
        url = f"https://soundcloud.com/search/sounds?q={quote_plus(query)}"
        errors: list[ScrapeError] = []

        if render_js:
            html = self.browser.get_html(
                url, wait_for="networkidle", scroll_pages=scroll_pages
            )
        else:
            html = self.http.get_html(url)

        tracks = self._extract_tracks(html, max_results)

        if not tracks:
            errors.append(ScrapeError(
                url=url,
                message="No tracks extracted. SoundCloud is JS-heavy — try render_js=True.",
            ))

        return ScrapeResult(
            data=tracks,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _extract_tracks(self, html: str, max_results: int) -> list[dict[str, Any]]:
        """Extract track data from SoundCloud HTML."""
        tracks: list[dict[str, Any]] = []

        # Try embedded Hydration data
        json_tracks = self._extract_from_hydration(html, max_results)
        if json_tracks:
            return json_tracks

        # Fallback: parse rendered HTML
        soup = self.parse_html(html)

        for item in soup.select(
            ".searchList__item, "
            ".soundList__item, "
            "li.searchList__item, "
            "article"
        ):
            track: dict[str, Any] = {}

            # Title
            title_el = item.select_one(
                "a.soundTitle__title span, "
                "a[href*='/'] span.sc-truncate"
            )
            if title_el:
                track["title"] = title_el.get_text(strip=True)

            # Artist
            artist_el = item.select_one(
                "a.soundTitle__username span, "
                "a[href] span.soundTitle__usernameText"
            )
            if artist_el:
                track["artist"] = artist_el.get_text(strip=True)

            # URL
            link = item.select_one("a[href*='/']")
            if link:
                href = str(link.get("href", ""))
                if href.startswith("/"):
                    href = "https://soundcloud.com" + href
                track["url"] = href

            # Play count
            plays_el = item.select_one(
                ".sc-ministats-plays span[aria-hidden], "
                "[class*='playbackCount']"
            )
            if plays_el:
                track["plays"] = plays_el.get_text(strip=True)

            # Duration
            duration_el = item.select_one(
                ".soundTitle__duration span[aria-hidden], "
                "[class*='duration']"
            )
            if duration_el:
                track["duration"] = duration_el.get_text(strip=True)

            if track.get("title"):
                tracks.append(track)

            if len(tracks) >= max_results:
                break

        return tracks

    def _extract_from_hydration(
        self, html: str, max_results: int
    ) -> list[dict[str, Any]]:
        """Extract data from SoundCloud's __sc_hydration JSON."""
        tracks: list[dict[str, Any]] = []

        match = re.search(
            r"window\.__sc_hydration\s*=\s*(\[.*?\]);\s*</script>",
            html, re.DOTALL,
        )
        if not match:
            return tracks

        try:
            hydration = json.loads(match.group(1))
        except json.JSONDecodeError:
            return tracks

        for entry in hydration:
            # SoundCloud's hydration array is heterogeneous — entries may be
            # strings or other JSON values, not just dicts. Guard every access.
            if not isinstance(entry, dict):
                continue
            data = entry.get("data", {})
            if not isinstance(data, dict):
                continue
            # Look for search result collections
            collection = data.get("collection", [])
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, dict) or item.get("kind") != "track":
                    continue

                user = item.get("user") or {}
                if not isinstance(user, dict):
                    user = {}
                tracks.append({
                    "title": item.get("title", ""),
                    "artist": user.get("username", ""),
                    "url": item.get("permalink_url", ""),
                    "plays": item.get("playback_count"),
                    "likes": item.get("likes_count"),
                    "duration_ms": item.get("duration"),
                    "genre": item.get("genre", ""),
                    "created_at": item.get("created_at", ""),
                })

                if len(tracks) >= max_results:
                    return tracks

        return tracks
