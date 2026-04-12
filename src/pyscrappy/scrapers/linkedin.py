"""LinkedIn public job search scraper (experimental).

.. warning::

    LinkedIn aggressively rate-limits and blocks scrapers.
    This scraper only accesses publicly visible job listings
    (no login required). Use generous rate limits.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class LinkedInJobsScraper(BaseScraper):
    """Scrape public LinkedIn job postings (experimental).

    Usage::

        config = ScraperConfig(rate_limit=5.0)  # be very gentle
        with LinkedInJobsScraper(config) as scraper:
            result = scraper.scrape(
                query="python developer",
                location="San Francisco",
                max_pages=2,
            )
    """

    name = "linkedin"

    def scrape(  # type: ignore[override]
        self,
        query: str,
        location: str = "",
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Search LinkedIn's public job board.

        Args:
            query: Job title or keywords.
            location: City, state, or country.
            max_pages: Number of result pages to scrape (25 jobs per page).

        Returns:
            ScrapeResult with job posting data.
        """
        jobs: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []

        for page in range(max_pages):
            start = page * 25
            url = (
                f"https://www.linkedin.com/jobs/search/?"
                f"keywords={quote_plus(query)}"
                f"&location={quote_plus(location)}"
                f"&start={start}"
            )
            visited.append(url)

            try:
                soup = self.fetch_and_parse(url)
            except Exception as exc:
                errors.append(ScrapeError(url=url, message=str(exc)))
                break

            # Check if we got an auth wall
            if soup.find("form", class_="login__form"):
                errors.append(ScrapeError(
                    url=url,
                    message="LinkedIn requires authentication for this page.",
                ))
                break

            page_jobs = self._parse_job_cards(soup)
            if not page_jobs:
                break
            jobs.extend(page_jobs)

        return ScrapeResult(
            data=jobs,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=errors,
        )

    def _parse_job_cards(self, soup: Any) -> list[dict[str, Any]]:
        """Parse job cards from LinkedIn's public job search page."""
        jobs: list[dict[str, Any]] = []

        for card in soup.select(
            ".base-card, .job-search-card, .base-search-card--link"
        ):
            job = self._parse_single_card(card)
            if job and job.get("title"):
                jobs.append(job)

        return jobs

    def _parse_single_card(self, card: Tag) -> dict[str, Any]:
        """Extract data from a single job card."""
        job: dict[str, Any] = {}

        # Title
        title_el = card.select_one(
            ".base-search-card__title, .base-card__full-link span"
        )
        if title_el:
            job["title"] = title_el.get_text(strip=True)

        # Company
        company_el = card.select_one(
            ".base-search-card__subtitle a, .base-search-card__subtitle"
        )
        if company_el:
            job["company"] = company_el.get_text(strip=True)

        # Location
        location_el = card.select_one(".job-search-card__location")
        if location_el:
            job["location"] = location_el.get_text(strip=True)

        # Link
        link = card.select_one("a.base-card__full-link, a.base-search-card--link")
        if link:
            job["url"] = str(link.get("href", "")).split("?")[0]

        # Date
        time_el = card.select_one("time")
        if time_el and isinstance(time_el, Tag):
            job["posted"] = time_el.get("datetime", time_el.get_text(strip=True))

        # Salary (when shown)
        salary_el = card.select_one(".job-search-card__salary-info")
        if salary_el:
            job["salary"] = salary_el.get_text(strip=True)

        return job
