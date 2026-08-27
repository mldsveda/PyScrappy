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
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scraper: str = ""


@dataclass
class ScrapeResult:
    """Unified result from any scraper.

    ``data`` is always a list of dicts — one dict per scraped item.
    Call ``.to_dataframe()`` for a pandas DataFrame, ``.to_json()`` for
    JSON, ``.to_csv()`` for CSV text, ``.to_ndjson()`` for NDJSON,
    ``.to_yaml()`` for YAML, ``.to_markdown()`` for clean,
    LLM-ready Markdown, or ``.save(path)`` to write by file extension.
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
                raw_level = str(heading.get("level") or "h2")
                level = (
                    max(1, min(int(raw_level[1:]), 6))
                    if raw_level[:1].lower() == "h" and raw_level[1:].isdigit()
                    else 2
                )
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

        def escape_cell(value: Any) -> str:
            return (
                str(value)
                .replace("\\", "\\\\")
                .replace("|", "\\|")
                .replace("\n", "<br>")
                .replace("\r", "")
            )

        headers: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for header in row:
                if header not in seen:
                    seen.add(header)
                    headers.append(header)
        lines = [
            "| " + " | ".join(escape_cell(header) for header in headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(escape_cell(row.get(h, "")) for h in headers) + " |")
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

    def to_csv(self) -> str:
        """Return ``data`` as CSV text.

        Uses pandas when available (``to_dataframe().to_csv(index=False)``).
        Nested / non-scalar cell values are stringified. Falls back to the
        stdlib ``csv`` module when pandas is not installed.
        """
        # Empty data is "" in both paths (pandas' DataFrame([]).to_csv() would
        # otherwise return a lone newline), so guard before either branch.
        if not self.data:
            return ""
        try:
            return self.to_dataframe().to_csv(index=False)
        except ImportError:
            import csv
            import io

            # Union of keys preserves column order from the first row, then
            # appends any later keys in encounter order.
            fieldnames: list[str] = []
            seen: set[str] = set()
            for row in self.data:
                for key in row:
                    if key not in seen:
                        seen.add(key)
                        fieldnames.append(key)
            buf = io.StringIO()
            # lineterminator="\n" so the stdlib fallback matches pandas' "\n"
            # output (DictWriter defaults to "\r\n"); output is identical either way.
            writer = csv.DictWriter(
                buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            for row in self.data:
                writer.writerow({k: row.get(k, "") for k in fieldnames})
            return buf.getvalue()

    def to_ndjson(self) -> str:
        """Return ``data`` as NDJSON (one JSON object per line).

        This is the standard interchange format for LLM fine-tuning sets,
        log pipelines, and streaming consumers.  Only ``data`` rows are
        emitted — no metadata/errors envelope.
        """
        import json

        if not self.data:
            return ""
        return "\n".join(json.dumps(row, default=str, ensure_ascii=False) for row in self.data)

    def to_yaml(self) -> str:
        """Return the full result envelope as YAML.

        Dumps ``{data, metadata, errors}`` — the same structure as
        :meth:`to_json`.

        Raises:
            ImportError: If PyYAML is not installed.
        """
        import json

        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for to_yaml(). Install it with: pip install 'pyscrappy[yaml]'"
            ) from None

        envelope = {
            "data": self.data,
            "metadata": {
                "source_urls": self.metadata.source_urls,
                "total_pages": self.metadata.total_pages,
                "timestamp": self.metadata.timestamp,
                "scraper": self.metadata.scraper,
            },
            "errors": [
                {"url": e.url, "message": e.message, "selector": e.selector} for e in self.errors
            ],
        }
        # Coerce to basic types via a JSON round-trip (mirrors to_json's
        # default=str), so safe_dump never has to emit Python-specific tags for a
        # non-primitive value in data — the output stays safe_load round-trippable.
        envelope = json.loads(json.dumps(envelope, default=str))
        return yaml.safe_dump(
            envelope, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

    def save(self, path: str) -> None:
        """Write the result to ``path``, choosing format from the extension.

        Supported extensions: ``.json`` → :meth:`to_json`, ``.csv`` →
        :meth:`to_csv`, ``.md`` → :meth:`to_markdown`, ``.ndjson`` /
        ``.jsonl`` → :meth:`to_ndjson`, ``.yaml`` / ``.yml`` →
        :meth:`to_yaml`.
        """
        from pathlib import Path as _Path

        p = _Path(path)
        suffix = p.suffix.lower()
        if suffix == ".json":
            content = self.to_json()
        elif suffix == ".csv":
            content = self.to_csv()
        elif suffix == ".md":
            content = self.to_markdown()
        elif suffix in (".ndjson", ".jsonl"):
            content = self.to_ndjson()
        elif suffix in (".yaml", ".yml"):
            content = self.to_yaml()
        else:
            raise ValueError(
                f"Unsupported extension {suffix!r} for save(); "
                "use .json, .csv, .md, .ndjson, .jsonl, .yaml, or .yml"
            )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
