"""Live integration tests for the scrapers that should work without a proxy.

These hit the real network and are **opt-in** (deselected by default). Run with::

    pytest -m integration

Purpose: catch when a target site changes its markup and silently breaks a
scraper. The key nuance is telling apart two failure modes:

* the scraper is **broken** (a successful fetch yields no data) -> FAIL
* we were **blocked / rate-limited** (network error, 403/429, challenge page)
  -> SKIP, because that's an environment/IP problem, not a code regression

So a red run means "a scraper genuinely broke", not "the CI runner's IP is
flagged today".

Caveat: some sites (e.g. Newegg) *soft-throttle* by returning a ``200`` with a
stripped page and no blocking signal. That is indistinguishable from a real
selector break, so it is (correctly) reported as a FAILURE, not a skip. If a
site-specific test fails, first re-run it from a clean IP before assuming the
scraper is broken.
"""

from __future__ import annotations

import os

import pytest

from pyscrappy import (
    AmazonScraper,
    IKEAScraper,
    ImageSearchScraper,
    IMDBScraper,
    LinkedInJobsScraper,
    NeweggScraper,
    NewsScraper,
    StockScraper,
    WikipediaScraper,
    YouTubeScraper,
    ZomatoScraper,
    scrape,
)
from pyscrappy.core.models import ScrapeResult

pytestmark = pytest.mark.integration

# Error-message fragments that indicate blocking/rate-limiting rather than a
# broken scraper. When a result's errors match these, we skip.
_BLOCK_HINTS = (
    "blocks automated",
    "anti-bot",
    "captcha",
    "proxy",
    "rate-limit",
    "429",
    "403",
    "503",
    "timeout",
    "failed to fetch",
    "human verification",
    "requires js",
    "requires an authenticated",
)


def assert_scraped(result: ScrapeResult, *, min_items: int = 1) -> None:
    """Assert the scraper returned data, or skip if it was clearly blocked.

    - data present  -> pass
    - blocked/rate-limited (per error text) -> skip
    - empty with no blocking signal -> FAIL (the scraper likely broke)
    """
    if len(result.data) >= min_items:
        return

    err_text = " ".join(e.message.lower() for e in result.errors)
    if any(hint in err_text for hint in _BLOCK_HINTS):
        pytest.skip(f"blocked/rate-limited, not a scraper regression: {err_text[:120]}")

    pytest.fail(
        "scraper returned no data and reported no blocking signal - its "
        f"selectors/markup likely broke. errors={[e.message for e in result.errors]}"
    )


class TestLiveCore:
    def test_generic_url(self):
        result = scrape("https://en.wikipedia.org/wiki/Web_scraping")
        assert_scraped(result)
        assert "text" in result.data[0]

    def test_wikipedia(self):
        with WikipediaScraper() as s:
            result = s.scrape(query="Python (programming language)", mode="paragraphs")
        assert_scraped(result, min_items=3)

    def test_stock(self):
        with StockScraper() as s:
            result = s.scrape(symbol="AAPL", mode="quote")
        assert_scraped(result)

    def test_news(self):
        with NewsScraper() as s:
            result = s.scrape(feed_url="http://feeds.bbci.co.uk/news/rss.xml", max_articles=5)
        assert_scraped(result)

    def test_image_search(self):
        with ImageSearchScraper() as s:
            result = s.scrape(query="golden retriever", max_images=3)
        assert_scraped(result)

    def test_youtube(self):
        with YouTubeScraper() as s:
            result = s.scrape(query="python tutorial", max_results=3)
        assert_scraped(result)

    def test_linkedin_jobs(self):
        with LinkedInJobsScraper() as s:
            result = s.scrape(query="data scientist", location="London", max_pages=1)
        assert_scraped(result)

    def test_zomato(self):
        with ZomatoScraper() as s:
            result = s.scrape(city="Delhi", max_results=5)
        assert_scraped(result)


class TestLiveEcommerce:
    def test_amazon(self):
        with AmazonScraper() as s:
            result = s.scrape(query="headphones", max_pages=1)
        assert_scraped(result)

    def test_newegg(self):
        with NeweggScraper() as s:
            result = s.scrape(query="graphics card", max_pages=1)
        assert_scraped(result)

    def test_ikea(self):
        with IKEAScraper() as s:
            result = s.scrape(query="desk", max_results=5)
        assert_scraped(result)


class TestLiveApiKeyed:
    def test_imdb_via_omdb(self):
        if not os.environ.get("OMDB_API_KEY"):
            pytest.skip("OMDB_API_KEY not set")
        with IMDBScraper() as s:
            result = s.scrape(query="tt1375666")
        assert_scraped(result)
