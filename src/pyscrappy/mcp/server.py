"""MCP server exposing PyScrappy scrapers as agent tools.

Each tool wraps a PyScrappy scraper and returns the ``ScrapeResult`` as a JSON
string, which is the shape MCP clients expect. Scrapers run in a worker thread
because PyScrappy's HTTP/browser stack is synchronous and we must not block the
event loop.
"""

from __future__ import annotations

import anyio

from mcp.server.fastmcp import FastMCP

from pyscrappy import (
    IMDBScraper,
    NewsScraper,
    ScrapeResult,
    StockScraper,
    WikipediaScraper,
    scrape as _scrape_url,
)

mcp = FastMCP("pyscrappy")


async def _run(fn, /, *args, **kwargs) -> str:
    """Run a synchronous scraper off the event loop and return JSON."""
    result: ScrapeResult = await anyio.to_thread.run_sync(
        lambda: fn(*args, **kwargs)
    )
    return result.to_json()


@mcp.tool()
async def scrape_url(
    url: str,
    selectors: dict[str, str] | None = None,
    max_pages: int = 1,
    render_js: bool = False,
) -> str:
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
    )


@mcp.tool()
async def scrape_wikipedia(query: str, mode: str = "full") -> str:
    """Fetch a Wikipedia article.

    Args:
        query: Article title or search term, e.g. "Model Context Protocol".
        mode: "full", "paragraphs", or "headers".
    """
    with WikipediaScraper() as ws:
        return await _run(ws.scrape, query=query, mode=mode)


@mcp.tool()
async def scrape_stock(symbol: str, mode: str = "quote", period: str = "1mo") -> str:
    """Fetch stock market data from Yahoo Finance.

    Args:
        symbol: Ticker symbol, e.g. "AAPL", "GOOGL".
        mode: "quote", "history", or "profile".
        period: History window when mode="history", e.g. "1mo", "1y".
    """
    with StockScraper() as ss:
        return await _run(ss.scrape, symbol=symbol, mode=mode, period=period)


@mcp.tool()
async def scrape_news(
    feed_url: str | None = None,
    site_url: str | None = None,
    article_url: str | None = None,
    max_articles: int = 50,
) -> str:
    """Fetch news articles from an RSS feed, a news site, or a single article.

    Provide exactly one of feed_url, site_url, or article_url.

    Args:
        feed_url: Direct URL to an RSS/Atom feed.
        site_url: News site URL — its feed is auto-discovered.
        article_url: A single article URL to extract full text from.
        max_articles: Max articles to return from a feed (default 50).
    """
    with NewsScraper() as ns:
        return await _run(
            ns.scrape,
            feed_url=feed_url,
            site_url=site_url,
            article_url=article_url,
            max_articles=max_articles,
        )


@mcp.tool()
async def scrape_imdb(genre: str | None = None, max_pages: int = 1) -> str:
    """Search IMDB titles by genre.

    Args:
        genre: A genre name, e.g. "sci-fi", "comedy".
        max_pages: Pages of results to scrape (default 1).
    """
    with IMDBScraper() as ims:
        return await _run(ims.scrape, genre=genre, max_pages=max_pages)


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
