"""Image search scraper — download images from search engines."""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote_plus

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult

logger = logging.getLogger("pyscrappy.image_search")


class ImageSearchScraper(BaseScraper):
    """Search for images and optionally download them.

    Usage::

        with ImageSearchScraper() as scraper:
            # Search and get image URLs
            result = scraper.scrape(query="golden retriever", max_images=20)

            # Search and download to a folder
            result = scraper.scrape(
                query="golden retriever",
                max_images=20,
                download_to="./images",
            )
    """

    name = "image_search"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_images: int = 20,
        engine: str = "bing",
        download_to: str | None = None,
    ) -> ScrapeResult:
        """Search for images.

        Args:
            query: Search query string.
            max_images: Maximum number of images to return.
            engine: Search engine to use — ``"bing"`` or ``"google"``.
            download_to: If provided, download images to this directory.

        Returns:
            ScrapeResult with image URLs and metadata.
        """
        if engine == "google":
            images, url = self._search_google(query, max_images)
        else:
            images, url = self._search_bing(query, max_images)

        if download_to:
            self._download_images(images, download_to)

        return ScrapeResult(
            data=images,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    async def scrape_async(  # type: ignore[override]
        self,
        query: str,
        max_images: int = 20,
        engine: str = "bing",
        download_to: str | None = None,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` (same args/returns)."""
        if engine == "google":
            images, url = await self._search_google_async(query, max_images)
        else:
            images, url = await self._search_bing_async(query, max_images)

        if download_to:
            await self._download_images_async(images, download_to)

        return ScrapeResult(
            data=images,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _bing_url(self, query: str, max_images: int) -> str:
        return (
            f"https://www.bing.com/images/search?q={quote_plus(query)}&first=1&count={max_images}"
        )

    def _search_bing(self, query: str, max_images: int) -> tuple[list[dict[str, Any]], str]:
        """Search Bing Images (server-rendered, no JS needed)."""
        url = self._bing_url(query, max_images)
        soup = self.fetch_and_parse(url)
        return self._parse_bing(soup, url, max_images), url

    async def _search_bing_async(
        self, query: str, max_images: int
    ) -> tuple[list[dict[str, Any]], str]:
        """Async counterpart to :meth:`_search_bing`."""
        url = self._bing_url(query, max_images)
        soup = await self.fetch_and_parse_async(url)
        return self._parse_bing(soup, url, max_images), url

    def _parse_bing(self, soup: Any, url: str, max_images: int) -> list[dict[str, Any]]:
        """Extract image records from a parsed Bing results page."""
        images: list[dict[str, Any]] = []
        for item in soup.select("a.iusc"):
            # Bing stores image metadata in the 'm' attribute as JSON
            m_attr = item.get("m", "")
            if not m_attr:
                continue
            import json

            try:
                m_data = json.loads(str(m_attr))
            except (json.JSONDecodeError, TypeError):
                continue

            img_url = m_data.get("murl", "")
            if not img_url:
                continue

            images.append(
                {
                    "url": img_url,
                    "thumbnail": m_data.get("turl", ""),
                    "title": m_data.get("t", ""),
                    "source_page": m_data.get("purl", ""),
                    "width": m_data.get("mw"),
                    "height": m_data.get("mh"),
                }
            )

            if len(images) >= max_images:
                break

        # Fallback: extract from img tags if the above found nothing
        if not images:
            for img in soup.find_all("img", src=True):
                src = str(img["src"])
                if src.startswith("http") and "bing.com/th" not in src:
                    images.append(
                        {
                            "url": src,
                            "alt": img.get("alt", ""),
                        }
                    )
                    if len(images) >= max_images:
                        break

        return images

    def _google_url(self, query: str) -> str:
        return f"https://www.google.com/search?q={quote_plus(query)}&tbm=isch"

    def _search_google(self, query: str, max_images: int) -> tuple[list[dict[str, Any]], str]:
        """Search Google Images (basic HTML — limited results without JS)."""
        url = self._google_url(query)
        soup = self.fetch_and_parse(url)
        return self._parse_google(soup, url, max_images), url

    async def _search_google_async(
        self, query: str, max_images: int
    ) -> tuple[list[dict[str, Any]], str]:
        """Async counterpart to :meth:`_search_google`."""
        url = self._google_url(query)
        soup = await self.fetch_and_parse_async(url)
        return self._parse_google(soup, url, max_images), url

    def _parse_google(self, soup: Any, url: str, max_images: int) -> list[dict[str, Any]]:
        """Extract image records from a parsed Google results page."""
        images: list[dict[str, Any]] = []
        for img in soup.find_all("img", src=True):
            src = str(img["src"])
            # Skip Google's tracking pixel and logo
            if not src.startswith("http") or "google.com/images" in src:
                continue
            images.append(
                {
                    "url": src,
                    "alt": img.get("alt", ""),
                }
            )
            if len(images) >= max_images:
                break

        return images

    def _download_images(self, images: list[dict[str, Any]], directory: str) -> None:
        """Download images to a local directory."""
        os.makedirs(directory, exist_ok=True)

        for i, img in enumerate(images):
            img_url = img.get("url", "")
            if not img_url:
                continue

            ext = self._guess_extension(img_url)
            filename = os.path.join(directory, f"image_{i + 1:04d}{ext}")

            try:
                resp = self.http.get(img_url)
                with open(filename, "wb") as f:
                    f.write(resp.content)
                img["local_path"] = filename
                logger.info("Downloaded %s", filename)
            except Exception as exc:
                logger.warning("Failed to download %s: %s", img_url, exc)

    async def _download_images_async(self, images: list[dict[str, Any]], directory: str) -> None:
        """Async counterpart to :meth:`_download_images`."""
        os.makedirs(directory, exist_ok=True)

        for i, img in enumerate(images):
            img_url = img.get("url", "")
            if not img_url:
                continue

            ext = self._guess_extension(img_url)
            filename = os.path.join(directory, f"image_{i + 1:04d}{ext}")

            try:
                resp = await self.async_http.get(img_url)
                with open(filename, "wb") as f:
                    f.write(resp.content)
                img["local_path"] = filename
                logger.info("Downloaded %s", filename)
            except Exception as exc:
                logger.warning("Failed to download %s: %s", img_url, exc)

    @staticmethod
    def _guess_extension(url: str) -> str:
        """Guess file extension from URL."""
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"):
            if ext in url.lower():
                return ext
        return ".jpg"
