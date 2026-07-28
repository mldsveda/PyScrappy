"""An example PyScrappy scraper plugin.

Rename this package to `pyscrappy_<thing>` and adapt `ExampleScraper` to your
source. Everything a built-in scraper can do is available here via `BaseScraper`:
``self.fetch_html``, ``self.fetch_and_parse``, ``self.http``, ``self.browser``,
retries, rate limiting, proxies, and caching (all driven by ``self.config``).
"""

from __future__ import annotations

from typing import Any

from pyscrappy import BaseScraper
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult


class ExampleScraper(BaseScraper):
    """Scrape example.com and return its title and first paragraph.

    Replace this with your own logic. The only contract is: implement
    ``scrape`` and return a ``ScrapeResult`` whose ``data`` is a list of dicts.
    """

    name = "example"

    def scrape(self, url: str = "https://example.com", **kwargs: Any) -> ScrapeResult:
        soup = self.fetch_and_parse(url)

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        first_p = soup.find("p")
        paragraph = first_p.get_text(strip=True) if first_p else ""

        return ScrapeResult(
            data=[{"url": url, "title": title, "paragraph": paragraph}],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )


__all__ = ["ExampleScraper"]
