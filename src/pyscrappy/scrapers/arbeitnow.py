"""Arbeitnow job board scraper (via the public Arbeitnow API).

Uses the public Arbeitnow job-board API (no key required). The API returns
paginated job postings; keyword, location, remote and job-type filtering is
applied locally because the source only supports page selection.

Please attribute Arbeitnow (https://www.arbeitnow.com) and keep requests
moderate. Requests are spaced by ``ScraperConfig.rate_limit`` (1.0 second by
default).
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult

_API = "https://www.arbeitnow.com/api/job-board-api"
_SITE = "https://www.arbeitnow.com"


class ArbeitnowScraper(BaseScraper):
    """Search job postings on Arbeitnow.

    Usage::

        with ArbeitnowScraper() as scraper:
            result = scraper.scrape(query="python", location="Berlin", remote=True)

        # Async
        result = await scraper.scrape_async(query="backend", max_pages=2)
    """

    name = "arbeitnow"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        query: str = "",
        location: str = "",
        remote: bool | None = None,
        job_type: str | None = None,
        max_pages: int = 1,
        max_results: int = 20,
    ) -> ScrapeResult:
        """Search Arbeitnow job postings.

        Args:
            query: Case-insensitive text matched against job titles and tags.
            location: Case-insensitive text matched against the job location.
            remote: ``None`` does not filter; ``True``/``False`` requires a match.
            job_type: Case-insensitive job type matched against the API's list.
            max_pages: Maximum API pages to fetch (page 1 is the first page).
            max_results: Maximum jobs to return after filtering and deduplication.

        Returns:
            ScrapeResult with job data (title, company, location, url, tags,
            job_type, job_types, remote, created_at, description).
        """
        if max_pages <= 0 or max_results <= 0:
            return self._empty_result()

        jobs: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []
        seen: set[str] = set()
        saw_items = False
        url: str | None = self._build_url(1)

        while url and len(visited) < max_pages and len(jobs) < max_results:
            visited.append(url)
            try:
                payload = self._fetch_payload(url)
            except Exception as exc:
                errors.append(ScrapeError(url=url, message=str(exc)))
                break

            page_jobs, next_url, raw_count = self._process_payload(
                payload,
                seen,
                query=query,
                location=location,
                remote=remote,
                job_type=job_type,
                limit=max_results - len(jobs),
            )
            if raw_count:
                saw_items = True
            jobs.extend(page_jobs)

            if not next_url:
                break
            url = urljoin(url, next_url)
            if url in visited:
                break

        return self._build_result(jobs, visited, errors, saw_items=saw_items)

    async def scrape_async(  # type: ignore[override]
        self,
        query: str = "",
        location: str = "",
        remote: bool | None = None,
        job_type: str | None = None,
        max_pages: int = 1,
        max_results: int = 20,
    ) -> ScrapeResult:
        """Async counterpart to :meth:`scrape` (same args/returns)."""
        if max_pages <= 0 or max_results <= 0:
            return self._empty_result()

        jobs: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []
        seen: set[str] = set()
        saw_items = False
        url: str | None = self._build_url(1)

        while url and len(visited) < max_pages and len(jobs) < max_results:
            visited.append(url)
            try:
                payload = await self._fetch_payload_async(url)
            except Exception as exc:
                errors.append(ScrapeError(url=url, message=str(exc)))
                break

            page_jobs, next_url, raw_count = self._process_payload(
                payload,
                seen,
                query=query,
                location=location,
                remote=remote,
                job_type=job_type,
                limit=max_results - len(jobs),
            )
            if raw_count:
                saw_items = True
            jobs.extend(page_jobs)

            if not next_url:
                break
            url = urljoin(url, next_url)
            if url in visited:
                break

        return self._build_result(jobs, visited, errors, saw_items=saw_items)

    @staticmethod
    def _build_url(page: int) -> str:
        return f"{_API}?page={page}"

    def _fetch_payload(self, url: str) -> dict[str, Any]:
        return self._decode_payload(self.http.get_html(url))

    async def _fetch_payload_async(self, url: str) -> dict[str, Any]:
        return self._decode_payload(await self.async_http.get_html(url))

    @staticmethod
    def _decode_payload(raw: str) -> dict[str, Any]:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Invalid Arbeitnow response: expected a JSON object.")
        if not isinstance(payload.get("data"), list):
            raise ValueError("Invalid Arbeitnow response: 'data' must be a list.")
        return payload

    def _process_payload(
        self,
        payload: dict[str, Any],
        seen: set[str],
        *,
        query: str,
        location: str,
        remote: bool | None,
        job_type: str | None,
        limit: int,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        items = payload.get("data", [])
        raw_count = len(items) if isinstance(items, list) else 0
        jobs: list[dict[str, Any]] = []

        links = payload.get("links")
        next_url = links.get("next") if isinstance(links, dict) else None
        if not isinstance(next_url, str) or not next_url.strip():
            next_url = None

        for raw in items if isinstance(items, list) else []:
            if len(jobs) >= limit:
                break
            if not isinstance(raw, dict):
                continue

            job = self._parse(raw)
            if job is None:
                continue
            if not self._matches(
                job,
                query=query,
                location=location,
                remote=remote,
                job_type=job_type,
            ):
                continue

            key = self._dedup_key(raw, job)
            if key in seen:
                continue
            seen.add(key)
            jobs.append(job)

        return jobs, next_url, raw_count

    @classmethod
    def _parse(cls, item: dict[str, Any]) -> dict[str, Any] | None:
        title = cls._clean_str(item.get("title"))
        url = cls._clean_str(item.get("url"))
        if not title or not url:
            return None

        job_types = cls._str_list(item.get("job_types"))
        return {
            "title": title,
            "company": cls._clean_str(item.get("company_name")),
            "location": cls._clean_str(item.get("location")),
            "url": urljoin(_SITE, url),
            "tags": cls._str_list(item.get("tags")),
            "job_type": job_types[0] if job_types else None,
            "job_types": job_types,
            "remote": cls._as_bool(item.get("remote")),
            "created_at": cls._to_iso8601(item.get("created_at")),
            "description": cls._html_to_text(item.get("description")),
        }

    @classmethod
    def _matches(
        cls,
        job: dict[str, Any],
        *,
        query: str,
        location: str,
        remote: bool | None,
        job_type: str | None,
    ) -> bool:
        if remote is not None and job["remote"] != remote:
            return False

        if job_type:
            wanted = cls._fold(job_type)
            if wanted and not any(cls._fold(t) == wanted for t in job["job_types"]):
                return False

        if query:
            wanted = cls._fold(query)
            if wanted:
                haystack = [cls._fold(job["title"])]
                haystack.extend(cls._fold(tag) for tag in job["tags"])
                if not any(wanted in text for text in haystack):
                    return False

        if location:
            wanted = cls._fold(location)
            if wanted and wanted not in cls._fold(job["location"]):
                return False

        return True

    @staticmethod
    def _dedup_key(raw: dict[str, Any], job: dict[str, Any]) -> str:
        slug = raw.get("slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
        return job["url"]

    @staticmethod
    def _clean_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _str_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, (list, tuple, set)):
            values = list(value)
        else:
            values = [value]

        result: list[str] = []
        for item in values:
            text = cls._clean_str(item)
            if text is not None:
                result.append(text)
        return result

    @staticmethod
    def _fold(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip().casefold()
        decomposed = unicodedata.normalize("NFKD", text)
        return "".join(char for char in decomposed if not unicodedata.combining(char))

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return bool(value) if value is not None else False

    @staticmethod
    def _to_iso8601(value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                timestamp = float(text)
            except ValueError:
                try:
                    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                except ValueError:
                    return None
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat()
        elif isinstance(value, (int, float)):
            timestamp = float(value)
        else:
            return None

        try:
            if abs(timestamp) > 1e11:
                timestamp /= 1000.0
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            return None

    @staticmethod
    def _html_to_text(value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        text = html.unescape(value)
        text = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        return text.strip() or None

    def _build_result(
        self,
        jobs: list[dict[str, Any]],
        visited: list[str],
        errors: list[ScrapeError],
        *,
        saw_items: bool,
    ) -> ScrapeResult:
        result_errors = list(errors)
        if not jobs and not result_errors:
            url = visited[-1] if visited else _API
            message = "No jobs matched the requested filters." if saw_items else "No jobs found."
            result_errors.append(ScrapeError(url=url, message=message))

        return ScrapeResult(
            data=jobs,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=result_errors,
        )

    def _empty_result(self) -> ScrapeResult:
        return ScrapeResult(
            data=[],
            metadata=ScrapeMetadata(total_pages=0, scraper=self.name),
        )
