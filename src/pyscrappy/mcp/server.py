"""MCP server exposing PyScrappy scrapers as agent tools.

Each tool wraps a PyScrappy scraper and returns a typed ``ScrapeToolResult``, so
MCP clients get a declared output schema and validated ``structuredContent``
rather than an opaque JSON string. Scrapers run in a worker thread because
PyScrappy's HTTP/browser stack is synchronous and we must not block the event
loop.
"""

from __future__ import annotations

from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from pyscrappy import (
    AmazonScraper,
    IKEAScraper,
    ImageSearchScraper,
    IMDBScraper,
    LinkedInJobsScraper,
    NeweggScraper,
    NewsScraper,
    ScrapeResult,
    SoundCloudScraper,
    StockScraper,
    WikipediaScraper,
    YouTubeScraper,
    ZomatoScraper,
)
from pyscrappy import (
    scrape as _scrape_url,
)
from pyscrappy.core.config import ScraperConfig

mcp = FastMCP("pyscrappy")

# Agents tend to ask for the same data repeatedly within a session, so cache
# successful responses for a few minutes to cut latency and avoid rate limits.
# Hardcoded for now; a future version will make this configurable.
_CACHE_TTL = 300.0


def _config() -> ScraperConfig:
    return ScraperConfig(cache_ttl=_CACHE_TTL)


class ToolError(BaseModel):
    """A non-fatal problem encountered while scraping."""

    url: str
    message: str


class ScrapeToolResult(BaseModel):
    """Structured result returned by every PyScrappy MCP tool.

    ``data`` holds the scraped items. The item shape depends on the source (a
    movie, a stock quote, an article…), so it stays a list of free-form objects,
    while the envelope around it is typed and gives agents a stable schema.
    """

    data: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0
    scraper: str = ""
    source_urls: list[str] = Field(default_factory=list)
    errors: list[ToolError] = Field(default_factory=list)


def _to_result(result: ScrapeResult) -> ScrapeToolResult:
    return ScrapeToolResult(
        data=result.data,
        count=len(result.data),
        scraper=result.metadata.scraper,
        source_urls=result.metadata.source_urls,
        errors=[ToolError(url=e.url, message=e.message) for e in result.errors],
    )


async def _run(fn, /, *args, **kwargs) -> ScrapeToolResult:
    """Run a synchronous scraper off the event loop and return a typed result."""
    result: ScrapeResult = await anyio.to_thread.run_sync(
        lambda: fn(*args, **kwargs)
    )
    return _to_result(result)


@mcp.tool()
async def scrape_url(
    url: str,
    selectors: dict[str, str] | None = None,
    max_pages: int = 1,
    render_js: bool = False,
) -> ScrapeToolResult:
    """Scrape any URL and return structured text, links, images, tables and metadata.

    Args:
        url: The page to scrape.
        selectors: Optional CSS selectors, e.g. {"title": "h1", "price": ".amount"}.
        max_pages: Follow pagination up to this many pages (default 1).
        render_js: Render JavaScript with a browser backend (needs pyscrappy[browser]).
    """
    return await _run(
        _scrape_url,
        url,
        selectors=selectors,
        max_pages=max_pages,
        render_js=render_js,
        config=_config(),
    )


@mcp.tool()
async def scrape_wikipedia(query: str, mode: str = "full") -> ScrapeToolResult:
    """Fetch a Wikipedia article.

    Args:
        query: Article title or search term, e.g. "Model Context Protocol".
        mode: "full", "paragraphs", or "headers".
    """
    with WikipediaScraper(_config()) as ws:
        return await _run(ws.scrape, query=query, mode=mode)


@mcp.tool()
async def scrape_stock(symbol: str, mode: str = "quote", period: str = "1mo") -> ScrapeToolResult:
    """Fetch stock market data from Yahoo Finance.

    Args:
        symbol: Ticker symbol, e.g. "AAPL", "GOOGL".
        mode: "quote", "history", or "profile".
        period: History window when mode="history", e.g. "1mo", "1y".
    """
    with StockScraper(_config()) as ss:
        return await _run(ss.scrape, symbol=symbol, mode=mode, period=period)


@mcp.tool()
async def scrape_news(
    feed_url: str | None = None,
    site_url: str | None = None,
    article_url: str | None = None,
    max_articles: int = 50,
) -> ScrapeToolResult:
    """Fetch news articles from an RSS feed, a news site, or a single article.

    Provide exactly one of feed_url, site_url, or article_url.

    Args:
        feed_url: Direct URL to an RSS/Atom feed.
        site_url: News site URL — its feed is auto-discovered.
        article_url: A single article URL to extract full text from.
        max_articles: Max articles to return from a feed (default 50).
    """
    with NewsScraper(_config()) as ns:
        return await _run(
            ns.scrape,
            feed_url=feed_url,
            site_url=site_url,
            article_url=article_url,
            max_articles=max_articles,
        )


@mcp.tool()
async def search_images(query: str, max_images: int = 20, engine: str = "bing") -> ScrapeToolResult:
    """Search for images and return their URLs and metadata.

    Args:
        query: Image search query, e.g. "golden gate bridge".
        max_images: Maximum number of image results (default 20).
        engine: Search engine to use (default "bing").
    """
    with ImageSearchScraper(_config()) as iss:
        return await _run(
            iss.scrape, query=query, max_images=max_images, engine=engine
        )


@mcp.tool()
async def search_youtube(query: str, max_results: int = 20) -> ScrapeToolResult:
    """Search YouTube and return video titles, channels, links and metadata.

    Args:
        query: Search query, e.g. "model context protocol tutorial".
        max_results: Maximum number of videos to return (default 20).
    """
    with YouTubeScraper(_config()) as yts:
        return await _run(yts.scrape, query=query, max_results=max_results)


@mcp.tool()
async def search_linkedin_jobs(
    query: str, location: str = "", max_pages: int = 1
) -> ScrapeToolResult:
    """Search LinkedIn job postings.

    Args:
        query: Job title or keywords, e.g. "machine learning engineer".
        location: Location filter, e.g. "London" or "United Kingdom".
        max_pages: Pages of results to scrape (default 1).
    """
    with LinkedInJobsScraper(_config()) as ljs:
        return await _run(
            ljs.scrape, query=query, location=location, max_pages=max_pages
        )


@mcp.tool()
async def search_amazon(query: str, max_pages: int = 1) -> ScrapeToolResult:
    """Search Amazon products and return title, price, rating, and image.

    Args:
        query: Product search query, e.g. "wireless headphones".
        max_pages: Number of result pages to scrape (default 1).
    """
    with AmazonScraper(_config()) as az:
        return await _run(az.scrape, query=query, max_pages=max_pages)


@mcp.tool()
async def search_newegg(query: str, max_pages: int = 1) -> ScrapeToolResult:
    """Search Newegg for electronics and computer hardware.

    Args:
        query: Product search query, e.g. "graphics card".
        max_pages: Number of result pages to scrape (default 1).
    """
    with NeweggScraper(_config()) as ne:
        return await _run(ne.scrape, query=query, max_pages=max_pages)


@mcp.tool()
async def search_ikea(query: str, max_results: int = 24) -> ScrapeToolResult:
    """Search IKEA furniture and home products (name, type, price, rating).

    Args:
        query: Product search query, e.g. "desk" or "bookshelf".
        max_results: Maximum number of products to return (default 24).
    """
    with IKEAScraper(_config()) as ik:
        return await _run(ik.scrape, query=query, max_results=max_results)


@mcp.tool()
async def search_soundcloud(query: str, max_results: int = 20) -> ScrapeToolResult:
    """Search SoundCloud for tracks (title, artist, plays, likes, URL).

    Uses a browser backend to render SoundCloud's JavaScript, so it needs
    ``pyscrappy[browser]`` and is slower than the HTTP-based tools.

    Args:
        query: Search query, e.g. "lofi beats".
        max_results: Maximum number of tracks to return (default 20).
    """

    def _do() -> ScrapeResult:
        # The scraper drives Playwright's sync API, which pins the browser to
        # the thread that created it. Open, use and close it all inside this
        # one worker thread — never split the lifecycle across threads.
        with SoundCloudScraper(_config()) as scs:
            return scs.scrape(
                query=query,
                max_results=max_results,
                render_js=True,
                scroll_pages=1,
            )

    result: ScrapeResult = await anyio.to_thread.run_sync(_do)
    return _to_result(result)


@mcp.tool()
async def lookup_movie(query: str, max_pages: int = 1) -> ScrapeToolResult:
    """Look up movie/TV data from IMDB (via the OMDb API).

    Requires a free OMDb API key in the ``OMDB_API_KEY`` environment variable
    (get one at https://www.omdbapi.com/apikey.aspx). If it's missing, the tool
    returns an error explaining how to set it.

    Args:
        query: A title to search for (e.g. "inception"), or an IMDB id
            (e.g. "tt1375666") for a direct lookup.
        max_pages: Pages of search results to fetch, 10 per page (title search).
    """
    with IMDBScraper(_config()) as ims:
        return await _run(ims.scrape, query=query, max_pages=max_pages)


@mcp.tool()
async def scrape_zomato(
    city: str, query: str | None = None, max_results: int = 50
) -> ScrapeToolResult:
    """Search restaurants on Zomato by city.

    Args:
        city: City name, e.g. "Bangalore".
        query: Optional cuisine or restaurant search term.
        max_results: Maximum number of restaurants to return (default 50).
    """
    with ZomatoScraper(_config()) as zs:
        return await _run(
            zs.scrape, city=city, query=query, max_results=max_results
        )


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
