"""Data models for scraping results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ScrapeError:
    """A non-fatal error encountered during scraping."""

    url: str
    message: str
    selector: str | None = None


@dataclass
class ScrapeMetadata:
    """Metadata about a scrape operation."""

    source_urls: list[str] = field(default_factory=list)
    total_pages: int = 1
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    scraper: str = ""


@dataclass
class ScrapeResult:
    """Unified result from any scraper.

    ``data`` is always a list of dicts — one dict per scraped item.
    Call ``.to_dataframe()`` for a pandas DataFrame, ``.to_json()`` for
    JSON, or ``.to_markdown()`` for clean, LLM-ready Markdown.
    """

    data: list[dict[str, Any]]
    metadata: ScrapeMetadata = field(default_factory=ScrapeMetadata)
    errors: list[ScrapeError] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.data)

    def __bool__(self) -> bool:
        return len(self.data) > 0

    def to_dataframe(self) -> Any:
        """Convert ``data`` to a pandas DataFrame.

        Raises:
            ImportError: If pandas is not installed.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install 'pyscrappy[dataframe]'"
            ) from None
        return pd.DataFrame(self.data)

    def to_markdown(self) -> str:
        """Render the result as Markdown — clean, LLM-ready text.

        Rich pages scraped by :class:`GenericScraper` (with ``title``,
        ``text``, ``headings``, ``links``, ``tables``) are rendered as a
        readable document. Flat provider results (e.g. a movie's
        ``title``/``year``/``rating``) fall back to a key–value list.
        """
        blocks = [self._item_to_markdown(item) for item in self.data]
        return "\n\n---\n\n".join(b for b in blocks if b)

    @staticmethod
    def _item_to_markdown(item: dict[str, Any]) -> str:
        text = item.get("text")
        # Rich generic-scraper item: text is a dict with paragraphs/headings.
        if isinstance(text, dict):
            parts: list[str] = []
            title = (item.get("metadata") or {}).get("title")
            if title:
                parts.append(f"# {title}")
            for heading in text.get("headings", []):
                level = int(heading.get("level", "h2")[1:])
                parts.append(f"{'#' * level} {heading['text']}")
            body = text.get("text")
            if body:
                parts.append(body)
            for table in item.get("tables", []):
                md = ScrapeResult._table_to_markdown(table)
                if md:
                    parts.append(md)
            return "\n\n".join(parts)

        # Flat provider item: render as a key–value list.
        return "\n".join(f"**{k}:** {v}" for k, v in item.items())

    @staticmethod
    def _table_to_markdown(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return ""
        headers = list(rows[0].keys())
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        """Serialize the result to a JSON string."""
        import json

        return json.dumps(
            {
                "data": self.data,
                "metadata": {
                    "source_urls": self.metadata.source_urls,
                    "total_pages": self.metadata.total_pages,
                    "timestamp": self.metadata.timestamp,
                    "scraper": self.metadata.scraper,
                },
                "errors": [
                    {"url": e.url, "message": e.message, "selector": e.selector}
                    for e in self.errors
                ],
            },
            indent=indent,
            default=str,
        )
