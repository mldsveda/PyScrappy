"""Dictionary scraper (via the Free Dictionary API).

Uses dictionaryapi.dev (no key required). English by default.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_API = "https://api.dictionaryapi.dev/api/v2/entries/{lang}/{word}"


class DictionaryScraper(BaseScraper):
    """Look up word definitions.

    Usage::

        with DictionaryScraper() as scraper:
            result = scraper.scrape(word="serendipity")
            for entry in result.data:
                print(entry["part_of_speech"], entry["definition"])
    """

    name = "dictionary"

    def __init__(
        self,
        config: ScraperConfig | None = None,
        lang: str = "en",
    ) -> None:
        super().__init__(config)
        self.lang = lang

    def scrape(  # type: ignore[override]
        self,
        word: str,
    ) -> ScrapeResult:
        """Look up a word.

        Args:
            word: The word to define.

        Returns:
            ScrapeResult with one row per definition (part_of_speech,
            definition, example, synonyms, phonetic).
        """
        url = _API.format(lang=self.lang, word=quote(word))

        try:
            payload = json.loads(self.http.get_html(url))
        except Exception as exc:
            return self._err(url, str(exc))

        # The API returns a dict (with "title") when the word isn't found.
        if isinstance(payload, dict):
            return self._err(url, payload.get("title", f"No definition for {word!r}."))

        rows: list[dict[str, Any]] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            phonetic = entry.get("phonetic")
            for meaning in entry.get("meanings", []):
                pos = meaning.get("partOfSpeech")
                for definition in meaning.get("definitions", []):
                    rows.append(
                        {
                            "word": entry.get("word") or word,
                            "phonetic": phonetic,
                            "part_of_speech": pos,
                            "definition": definition.get("definition"),
                            "example": definition.get("example"),
                            "synonyms": definition.get("synonyms") or None,
                        }
                    )

        rows = [{k: v for k, v in r.items() if v is not None} for r in rows]
        errors = [] if rows else [ScrapeError(url=url, message=f"No definitions for {word!r}.")]
        return ScrapeResult(
            data=rows,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _err(self, url: str, message: str) -> ScrapeResult:
        return ScrapeResult(
            data=[],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=[ScrapeError(url=url, message=message)],
        )
