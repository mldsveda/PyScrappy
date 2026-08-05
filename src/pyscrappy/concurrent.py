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

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable

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


async def scrape_many_async(
    scraper_cls: type[BaseScraper],
    calls: list[dict[str, Any]],
    *,
    config: ScraperConfig | None = None,
    max_concurrency: int = _DEFAULT_WORKERS,
) -> list[ScrapeResult]:
    """Run ``scraper_cls.scrape_async(**call)`` for each call concurrently.

    A fresh scraper instance is created per call (and closed afterwards), so
    results are returned in the same order as ``calls``.

    Args:
        scraper_cls: A scraper class.
        calls: One kwargs dict per scrape.
        config: Optional shared config.
        max_concurrency: Maximum concurrent scrapes.

    Returns:
        A list of ``ScrapeResult`` in the same order as ``calls``.
    """

    workers = max(1, min(max_concurrency, len(calls))) if calls else 1
    semaphore = asyncio.Semaphore(workers)

    async def _one(call: dict[str, Any]) -> ScrapeResult:
        async with semaphore:
            async with scraper_cls(config) as scraper:
                return await scraper.scrape_async(**call)

    tasks = [asyncio.create_task(_one(call)) for call in calls]
    return await asyncio.gather(*tasks)


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


async def scrape_all_async(
    funcs: list[Callable[[], Awaitable[ScrapeResult]]],
    *,
    max_concurrency: int = _DEFAULT_WORKERS,
) -> list[ScrapeResult]:
    """Run several independent async scrape callables concurrently.

    Use this to mix different async scrapers in one batch. Each callable should
    return an awaitable ``ScrapeResult``. Results are returned in the same order
    as ``funcs``.

    Args:
        funcs: Zero-argument callables, each returning an awaitable
            ``ScrapeResult``.
        max_concurrency: Maximum number of concurrent scrapes.

    Returns:
        A list of ``ScrapeResult`` objects in the same order as ``funcs``.
    """

    workers = max(1, min(max_concurrency, len(funcs))) if funcs else 1
    semaphore = asyncio.Semaphore(workers)

    async def _one(func: Callable[[], Awaitable[ScrapeResult]]) -> ScrapeResult:
        async with semaphore:
            return await func()

    tasks = [asyncio.create_task(_one(f)) for f in funcs]
    return await asyncio.gather(*tasks)
