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
    Call ``.to_dataframe()`` to convert to a pandas DataFrame.
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
