"""Wikipedia scraper — extract articles, sections, and structured content."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult

_WIKI_BASE = "https://en.wikipedia.org/wiki/"
_BRACKET_RE = re.compile(r"\[.*?\]")


class WikipediaScraper(BaseScraper):
    """Scrape Wikipedia articles.

    Usage::

        with WikipediaScraper() as ws:
            # Full article
            result = ws.scrape(query="Python (programming language)")

            # Just paragraphs
            result = ws.scrape(query="Python (programming language)", mode="paragraphs")

            # Just section headers
            result = ws.scrape(query="Python (programming language)", mode="headers")
    """

    name = "wikipedia"

    def __init__(self, config: ScraperConfig | None = None, lang: str = "en") -> None:
        super().__init__(config)
        self._lang = lang
        self._base = f"https://{lang}.wikipedia.org/wiki/"

    def scrape(  # type: ignore[override]
        self,
        query: str,
        mode: str = "full",
    ) -> ScrapeResult:
        """Scrape a Wikipedia article.

        Args:
            query: Article title or search term (e.g. ``"Python (programming language)"``).
            mode: What to extract:
                - ``"full"``: paragraphs, headers, infobox, links, and tables.
                - ``"paragraphs"``: only paragraph text.
                - ``"headers"``: only section headers.
                - ``"summary"``: first paragraph only.

        Returns:
            ScrapeResult where each item in ``data`` is a section or paragraph.
        """
        url = self._base + quote(query.replace(" ", "_"))
        html = self.fetch_html(url)
        soup = self.parse_html(html)

        # Check for disambiguation or missing page
        content_div = soup.find("div", id="mw-content-text")
        if not content_div or not isinstance(content_div, Tag):
            return ScrapeResult(
                data=[],
                metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            )

        if mode == "headers":
            data = self._extract_headers(content_div)
        elif mode == "paragraphs":
            data = self._extract_paragraphs(content_div)
        elif mode == "summary":
            data = self._extract_summary(content_div)
        else:
            data = self._extract_full(content_div, url)

        return ScrapeResult(
            data=data,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _extract_paragraphs(self, content: Tag) -> list[dict[str, Any]]:
        paragraphs: list[dict[str, Any]] = []
        for p in content.find_all("p"):
            text = self._clean_text(p.get_text())
            if text:
                paragraphs.append({"type": "paragraph", "text": text})
        return paragraphs

    def _extract_headers(self, content: Tag) -> list[dict[str, Any]]:
        headers: list[dict[str, Any]] = []
        for span in content.find_all("span", class_="mw-headline"):
            text = span.get_text(strip=True)
            if text:
                parent = span.parent
                level = parent.name if parent else "h2"
                headers.append({"type": "header", "level": level, "text": text})
        return headers

    def _extract_summary(self, content: Tag) -> list[dict[str, Any]]:
        for p in content.find_all("p"):
            text = self._clean_text(p.get_text())
            if text and len(text) > 50:
                return [{"type": "summary", "text": text}]
        return []

    def _extract_full(self, content: Tag, url: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        # Infobox
        infobox = content.find("table", class_="infobox")
        if infobox and isinstance(infobox, Tag):
            info_data = self._parse_infobox(infobox)
            if info_data:
                items.append({"type": "infobox", "data": info_data})

        # Walk through content elements in order
        parser_output = content.find("div", class_="mw-parser-output")
        if not parser_output:
            parser_output = content

        current_section = "Introduction"
        for element in parser_output.children:
            if not isinstance(element, Tag):
                continue

            if element.name in ("h2", "h3", "h4"):
                headline = element.find("span", class_="mw-headline")
                if headline:
                    current_section = headline.get_text(strip=True)
                    items.append({
                        "type": "header",
                        "level": element.name,
                        "text": current_section,
                    })

            elif element.name == "p":
                text = self._clean_text(element.get_text())
                if text:
                    items.append({
                        "type": "paragraph",
                        "section": current_section,
                        "text": text,
                    })

            elif element.name == "table" and "wikitable" in element.get("class", []):
                table_data = self._parse_table(element)
                if table_data:
                    items.append({
                        "type": "table",
                        "section": current_section,
                        "data": table_data,
                    })

        return items

    def _parse_infobox(self, table: Tag) -> dict[str, str]:
        data: dict[str, str] = {}
        for row in table.find_all("tr"):
            header = row.find("th")
            value = row.find("td")
            if header and value:
                key = header.get_text(strip=True)
                val = value.get_text(strip=True)
                if key and val:
                    data[key] = self._clean_text(val)
        return data

    def _parse_table(self, table: Tag) -> list[dict[str, str]]:
        rows = table.find_all("tr")
        if len(rows) < 2:
            return []

        headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
        if not headers:
            return []

        data: list[dict[str, str]] = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) == len(headers):
                data.append({
                    h: self._clean_text(c.get_text())
                    for h, c in zip(headers, cells)
                })
        return data

    def _clean_text(self, text: str) -> str:
        text = _BRACKET_RE.sub("", text)
        text = " ".join(text.split())
        return text.strip()
