"""Tests for pyscrappy.concurrent (scrape_many / scrape_all)."""

import time

from pyscrappy.concurrent import scrape_all, scrape_many
from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult


class _FakeScraper(BaseScraper):
    """A scraper that sleeps briefly and echoes its query, for timing tests."""

    name = "fake"

    def scrape(self, query: str = "", delay: float = 0.0) -> ScrapeResult:  # type: ignore[override]
        if delay:
            time.sleep(delay)
        return ScrapeResult(
            data=[{"query": query}],
            metadata=ScrapeMetadata(scraper=self.name),
        )


class TestScrapeMany:
    def test_runs_all_calls(self):
        calls = [{"query": "a"}, {"query": "b"}, {"query": "c"}]
        results = scrape_many(_FakeScraper, calls)
        assert len(results) == 3

    def test_order_preserved(self):
        calls = [{"query": q} for q in ["x", "y", "z"]]
        results = scrape_many(_FakeScraper, calls)
        assert [r.data[0]["query"] for r in results] == ["x", "y", "z"]

    def test_empty_calls(self):
        assert scrape_many(_FakeScraper, []) == []

    def test_actually_concurrent(self):
        # 4 calls each sleeping 0.2s: serial would be ~0.8s, concurrent ~0.2s.
        calls = [{"query": str(i), "delay": 0.2} for i in range(4)]
        start = time.monotonic()
        results = scrape_many(_FakeScraper, calls, max_workers=4)
        elapsed = time.monotonic() - start
        assert len(results) == 4
        assert elapsed < 0.6  # well under the 0.8s serial time


class TestScrapeAll:
    def test_runs_all_and_preserves_order(self):
        funcs = [
            lambda: _FakeScraper().scrape(query="one"),
            lambda: _FakeScraper().scrape(query="two"),
        ]
        results = scrape_all(funcs)
        assert [r.data[0]["query"] for r in results] == ["one", "two"]

    def test_empty(self):
        assert scrape_all([]) == []

    def test_concurrent(self):
        funcs = [lambda: _FakeScraper().scrape(query="q", delay=0.2) for _ in range(4)]
        start = time.monotonic()
        scrape_all(funcs, max_workers=4)
        assert time.monotonic() - start < 0.6
