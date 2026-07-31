"""Concurrent scraping helpers.

PyScrappy's scrapers are synchronous, but scraping is I/O-bound, so running
several scrapes at once (across different sites, or many queries against one)
parallelises the network waits for a real speedup. These helpers fan the sync
scrapers out over a thread pool without changing the scraper API.

Example::

    from pyscrappy import AmazonScraper
    from pyscrappy.concurrent import scrape_many

    # Run one scraper over many queries, concurrently.
    results = scrape_many(AmazonScraper, [{"query": q} for q in ["laptop", "phone"]])

    from pyscrappy.concurrent import scrape_all

    # Run several independent scrape calls at once.
    results = scrape_all([
        lambda: WikipediaScraper().scrape(query="Python"),
        lambda: NewsScraper().scrape(feed_url="https://..."),
    ])
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeResult

_DEFAULT_WORKERS = 8


def scrape_many(
    scraper_cls: type[BaseScraper],
    calls: list[dict[str, Any]],
    *,
    config: ScraperConfig | None = None,
    max_workers: int = _DEFAULT_WORKERS,
) -> list[ScrapeResult]:
    """Run ``scraper_cls.scrape(**call)`` for each call, concurrently.

    A fresh scraper instance is created per call (and closed afterwards), so
    this is thread-safe. Results are returned in the same order as ``calls``.

    Args:
        scraper_cls: A scraper class, e.g. ``AmazonScraper``.
        calls: One kwargs dict per scrape, e.g. ``[{"query": "laptop"}, ...]``.
        config: Optional shared config applied to every scraper.
        max_workers: Maximum concurrent scrapes.

    Returns:
        A list of ``ScrapeResult`` in the same order as ``calls``.
    """

    def _one(call: dict[str, Any]) -> ScrapeResult:
        with scraper_cls(config) as scraper:
            return scraper.scrape(**call)

    workers = max(1, min(max_workers, len(calls))) if calls else 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, calls))


def scrape_all(
    funcs: list[Callable[[], ScrapeResult]],
    *,
    max_workers: int = _DEFAULT_WORKERS,
) -> list[ScrapeResult]:
    """Run several independent scrape callables concurrently.

    Use this to mix different scrapers in one batch. Each callable should return
    a ``ScrapeResult``. Results are returned in the same order as ``funcs``.

    Args:
        funcs: Zero-arg callables, each performing one scrape.
        max_workers: Maximum concurrent scrapes.

    Returns:
        A list of ``ScrapeResult`` in the same order as ``funcs``.
    """
    workers = max(1, min(max_workers, len(funcs))) if funcs else 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda f: f(), funcs))
