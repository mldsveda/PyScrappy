"""Instagram scraper — profiles and hashtag posts.

.. note::

    Instagram requires authentication for most content. This scraper
    works with public profiles via the ``?__a=1&__d=dis`` JSON endpoint
    and falls back to HTML parsing. For full access, use the browser
    backend with ``render_js=True``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class InstagramScraper(BaseScraper):
    """Scrape public Instagram profiles and hashtag pages.

    Usage::

        with InstagramScraper() as scraper:
            # Public profile info
            result = scraper.scrape(username="natgeo")

            # Hashtag posts (requires browser)
            result = scraper.scrape(hashtag="photography", render_js=True, scroll_pages=2)
    """

    name = "instagram"

    def scrape(  # type: ignore[override]
        self,
        username: str | None = None,
        hashtag: str | None = None,
        max_posts: int = 20,
        render_js: bool = False,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Scrape Instagram data.

        Args:
            username: Instagram handle (without @).
            hashtag: Hashtag to search (without #).
            max_posts: Maximum number of posts to return.
            render_js: Use browser for JS rendering.
            scroll_pages: Number of scrolls for loading more posts.

        Returns:
            ScrapeResult with profile or post data.
        """
        if username:
            return self._scrape_profile(username, max_posts, render_js, scroll_pages)
        if hashtag:
            return self._scrape_hashtag(hashtag, max_posts, render_js, scroll_pages)
        raise ValueError("Provide either username or hashtag")

    def _scrape_profile(
        self, username: str, max_posts: int, render_js: bool, scroll_pages: int
    ) -> ScrapeResult:
        url = f"https://www.instagram.com/{username}/"
        errors: list[ScrapeError] = []

        if render_js:
            html = self.browser.get_html(
                url, wait_for="networkidle", scroll_pages=scroll_pages
            )
        else:
            html = self.http.get_html(url)

        data = self._extract_shared_data(html)
        if data:
            profile = self._parse_profile_json(data, username)
        else:
            profile = self._parse_profile_html(html, username)
            if not profile.get("username"):
                errors.append(ScrapeError(
                    url=url,
                    message="Could not extract profile data. Instagram may require login.",
                ))

        return ScrapeResult(
            data=[profile] if profile else [],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _scrape_hashtag(
        self, hashtag: str, max_posts: int, render_js: bool, scroll_pages: int
    ) -> ScrapeResult:
        url = f"https://www.instagram.com/explore/tags/{hashtag}/"
        errors: list[ScrapeError] = []

        if render_js:
            html = self.browser.get_html(
                url, wait_for="networkidle", scroll_pages=scroll_pages
            )
        else:
            html = self.http.get_html(url)

        data = self._extract_shared_data(html)
        posts: list[dict[str, Any]] = []

        if data:
            posts = self._parse_hashtag_json(data, max_posts)
        else:
            posts = self._parse_posts_html(html, max_posts)
            if not posts:
                errors.append(ScrapeError(
                    url=url,
                    message="Could not extract hashtag posts. Instagram may require login.",
                ))

        return ScrapeResult(
            data=posts,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _extract_shared_data(self, html: str) -> dict[str, Any] | None:
        """Extract the _sharedData JSON blob embedded in Instagram pages."""
        match = re.search(r"window\._sharedData\s*=\s*({.*?});</script>", html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _parse_profile_json(self, data: dict[str, Any], username: str) -> dict[str, Any]:
        """Parse profile data from _sharedData JSON."""
        profile: dict[str, Any] = {"username": username}

        try:
            user = (
                data.get("entry_data", {})
                .get("ProfilePage", [{}])[0]
                .get("graphql", {})
                .get("user", {})
            )
        except (IndexError, KeyError):
            return profile

        profile["full_name"] = user.get("full_name", "")
        profile["bio"] = user.get("biography", "")
        profile["followers"] = user.get("edge_followed_by", {}).get("count")
        profile["following"] = user.get("edge_follow", {}).get("count")
        profile["posts_count"] = user.get("edge_owner_to_timeline_media", {}).get("count")
        profile["is_verified"] = user.get("is_verified", False)
        profile["profile_pic"] = user.get("profile_pic_url_hd", "")
        profile["external_url"] = user.get("external_url", "")

        # Recent posts
        edges = (
            user.get("edge_owner_to_timeline_media", {}).get("edges", [])
        )
        profile["recent_posts"] = [
            {
                "caption": (
                    edge.get("node", {})
                    .get("edge_media_to_caption", {})
                    .get("edges", [{}])[0]
                    .get("node", {})
                    .get("text", "")
                    if edge.get("node", {}).get("edge_media_to_caption", {}).get("edges")
                    else ""
                ),
                "likes": edge.get("node", {}).get("edge_liked_by", {}).get("count"),
                "comments": edge.get("node", {}).get("edge_media_to_comment", {}).get("count"),
                "url": f"https://www.instagram.com/p/{edge.get('node', {}).get('shortcode', '')}/",
            }
            for edge in edges[:20]
        ]

        return profile

    def _parse_profile_html(self, html: str, username: str) -> dict[str, Any]:
        """Fallback: parse profile from rendered HTML."""
        soup = self.parse_html(html)
        profile: dict[str, Any] = {"username": username}

        # Try meta tags
        desc = soup.find("meta", attrs={"name": "description"})
        if desc:
            content = str(desc.get("content", ""))
            profile["meta_description"] = content

        title = soup.find("meta", property="og:title")
        if title:
            profile["full_name"] = str(title.get("content", "")).split("(")[0].strip()

        return profile

    def _parse_hashtag_json(
        self, data: dict[str, Any], max_posts: int
    ) -> list[dict[str, Any]]:
        """Parse hashtag data from _sharedData JSON."""
        posts: list[dict[str, Any]] = []

        try:
            tag_data = (
                data.get("entry_data", {})
                .get("TagPage", [{}])[0]
                .get("graphql", {})
                .get("hashtag", {})
            )
        except (IndexError, KeyError):
            return posts

        edges = tag_data.get("edge_hashtag_to_media", {}).get("edges", [])

        for edge in edges[:max_posts]:
            node = edge.get("node", {})
            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            posts.append({
                "caption": (
                    caption_edges[0].get("node", {}).get("text", "")
                    if caption_edges else ""
                ),
                "likes": node.get("edge_liked_by", {}).get("count"),
                "comments": node.get("edge_media_to_comment", {}).get("count"),
                "url": f"https://www.instagram.com/p/{node.get('shortcode', '')}/",
                "is_video": node.get("is_video", False),
            })

        return posts

    def _parse_posts_html(
        self, html: str, max_posts: int
    ) -> list[dict[str, Any]]:
        """Fallback: extract post links from rendered HTML."""
        soup = self.parse_html(html)
        posts: list[dict[str, Any]] = []
        seen: set[str] = set()

        for a in soup.select("a[href*='/p/']"):
            href = str(a.get("href", ""))
            if href in seen:
                continue
            seen.add(href)

            if href.startswith("/"):
                href = "https://www.instagram.com" + href

            posts.append({"url": href})
            if len(posts) >= max_posts:
                break

        return posts
