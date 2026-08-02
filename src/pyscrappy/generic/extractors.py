"""Extraction components for the generic scraper.

Each extractor takes a BeautifulSoup tree and returns structured data.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


class MetadataExtractor:
    """Extract page metadata: title, description, Open Graph tags, etc."""

    def extract(self, soup: BeautifulSoup, url: str = "") -> dict[str, Any]:
        meta: dict[str, Any] = {}

        # Title
        if soup.title and soup.title.string:
            meta["title"] = soup.title.string.strip()

        # Meta tags
        for tag in soup.find_all("meta"):
            name = tag.get("name", "") or tag.get("property", "")
            content = tag.get("content", "")
            if not name or not content:
                continue
            name = str(name).lower()
            if name == "description":
                meta["description"] = content
            elif name == "author":
                meta["author"] = content
            elif name in ("keywords",):
                meta["keywords"] = [k.strip() for k in content.split(",")]
            elif name.startswith("og:"):
                meta.setdefault("og", {})[name[3:]] = content
            elif name.startswith("twitter:"):
                meta.setdefault("twitter_card", {})[name[8:]] = content

        # Canonical URL
        canonical = soup.find("link", rel="canonical")
        if canonical and isinstance(canonical, Tag):
            meta["canonical_url"] = canonical.get("href", "")

        # Language
        html_tag = soup.find("html")
        if html_tag and isinstance(html_tag, Tag):
            lang = html_tag.get("lang")
            if lang:
                meta["language"] = str(lang)

        return meta


class TextExtractor:
    """Extract the main text content from a page using readability heuristics."""

    _BLOCK_TAGS = {"p", "div", "article", "section", "main", "blockquote", "li", "td", "pre"}
    _NOISE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"}
    _NOISE_CLASSES = re.compile(
        r"(nav|menu|sidebar|footer|header|comment|ad|social|share|related|widget|popup|modal)",
        re.IGNORECASE,
    )

    def extract(self, soup: BeautifulSoup) -> dict[str, Any]:
        # Remove noise elements
        clean = self._remove_noise(soup)

        # Try <article> or <main> first
        main_content = clean.find("article") or clean.find("main") or clean.find(role="main")

        if main_content and isinstance(main_content, Tag):
            paragraphs = self._get_paragraphs(main_content)
        else:
            paragraphs = self._get_paragraphs(clean)

        text = "\n\n".join(paragraphs)
        headings = self._get_headings(clean)

        return {
            "text": text,
            "paragraphs": paragraphs,
            "headings": headings,
            "word_count": len(text.split()),
        }

    def _remove_noise(self, soup: BeautifulSoup) -> BeautifulSoup:

        clean = BeautifulSoup(str(soup), "lxml")
        for tag in clean.find_all(self._NOISE_TAGS):
            tag.decompose()
        for tag in clean.find_all(attrs={"class": self._NOISE_CLASSES}):
            tag.decompose()
        for tag in clean.find_all(attrs={"id": self._NOISE_CLASSES}):
            tag.decompose()
        return clean

    def _get_paragraphs(self, element: Tag | BeautifulSoup) -> list[str]:
        paragraphs: list[str] = []
        for p in element.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 30:
                paragraphs.append(text)
        if not paragraphs:
            for tag in element.find_all(self._BLOCK_TAGS):
                text = tag.get_text(strip=True)
                if len(text) > 50:
                    paragraphs.append(text)
        return paragraphs

    def _get_headings(self, element: Tag | BeautifulSoup) -> list[dict[str, str]]:
        headings: list[dict[str, str]] = []
        for tag in element.find_all(re.compile(r"^h[1-6]$")):
            text = tag.get_text(strip=True)
            if text:
                headings.append({"level": tag.name, "text": text})
        return headings


class LinkExtractor:
    """Extract all links from a page."""

    def extract(self, soup: BeautifulSoup, base_url: str = "") -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue

            absolute = urljoin(base_url, href) if base_url else href
            if absolute in seen:
                continue
            seen.add(absolute)

            links.append(
                {
                    "url": absolute,
                    "text": a.get_text(strip=True),
                    "rel": " ".join(a.get("rel", [])),
                }
            )

        return links


class ImageExtractor:
    """Extract all images from a page."""

    def extract(self, soup: BeautifulSoup, base_url: str = "") -> list[dict[str, str]]:
        images: list[dict[str, str]] = []

        for img in soup.find_all("img"):
            src = str(img.get("src") or img.get("data-src") or img.get("data-lazy-src") or "")
            if not src:
                continue
            absolute = urljoin(base_url, src) if base_url else src
            images.append(
                {
                    "url": absolute,
                    "alt": str(img.get("alt") or ""),
                    "width": str(img.get("width") or ""),
                    "height": str(img.get("height") or ""),
                }
            )

        return images


class TableExtractor:
    """Extract HTML tables into lists of dicts."""

    def extract(self, soup: BeautifulSoup) -> list[list[dict[str, str]]]:
        tables: list[list[dict[str, str]]] = []

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue

            # Get headers from first row
            headers: list[str] = []
            first_row = rows[0]
            for cell in first_row.find_all(["th", "td"]):
                headers.append(cell.get_text(strip=True))

            if not headers:
                continue

            # Parse data rows
            table_data: list[dict[str, str]] = []
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) != len(headers):
                    continue
                row_dict = {}
                for header, cell in zip(headers, cells):
                    row_dict[header] = cell.get_text(strip=True)
                table_data.append(row_dict)

            if table_data:
                tables.append(table_data)

        return tables
