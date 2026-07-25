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
    ImageSearchScraper,
    IMDBScraper,
    LinkedInJobsScraper,
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
async def search_images(query: str, max_images: int = 20, engine: str = "bing") -> str:
    """Search for images and return their URLs and metadata.

    Args:
        query: Image search query, e.g. "golden gate bridge".
        max_images: Maximum number of image results (default 20).
        engine: Search engine to use (default "bing").
    """
    with ImageSearchScraper() as iss:
        return await _run(
            iss.scrape, query=query, max_images=max_images, engine=engine
        )


@mcp.tool()
async def search_youtube(query: str, max_results: int = 20) -> str:
    """Search YouTube and return video titles, channels, links and metadata.

    Args:
        query: Search query, e.g. "model context protocol tutorial".
        max_results: Maximum number of videos to return (default 20).
    """
    with YouTubeScraper() as yts:
        return await _run(yts.scrape, query=query, max_results=max_results)


@mcp.tool()
async def search_linkedin_jobs(
    query: str, location: str = "", max_pages: int = 1
) -> str:
    """Search LinkedIn job postings.

    Args:
        query: Job title or keywords, e.g. "machine learning engineer".
        location: Location filter, e.g. "London" or "United Kingdom".
        max_pages: Pages of results to scrape (default 1).
    """
    with LinkedInJobsScraper() as ljs:
        return await _run(
            ljs.scrape, query=query, location=location, max_pages=max_pages
        )


@mcp.tool()
async def search_soundcloud(query: str, max_results: int = 20) -> str:
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
        with SoundCloudScraper() as scs:
            return scs.scrape(
                query=query,
                max_results=max_results,
                render_js=True,
                scroll_pages=1,
            )

    result: ScrapeResult = await anyio.to_thread.run_sync(_do)
    return result.to_json()


@mcp.tool()
async def lookup_movie(query: str, max_pages: int = 1) -> str:
    """Look up movie/TV data from IMDB (via the OMDb API).

    Requires a free OMDb API key in the ``OMDB_API_KEY`` environment variable
    (get one at https://www.omdbapi.com/apikey.aspx). If it's missing, the tool
    returns an error explaining how to set it.

    Args:
        query: A title to search for (e.g. "inception"), or an IMDB id
            (e.g. "tt1375666") for a direct lookup.
        max_pages: Pages of search results to fetch, 10 per page (title search).
    """
    with IMDBScraper() as ims:
        return await _run(ims.scrape, query=query, max_pages=max_pages)


@mcp.tool()
async def scrape_zomato(city: str, query: str | None = None, max_results: int = 50) -> str:
    """Search restaurants on Zomato by city.

    Args:
        city: City name, e.g. "Bangalore".
        query: Optional cuisine or restaurant search term.
        max_results: Maximum number of restaurants to return (default 50).
    """
    with ZomatoScraper() as zs:
        return await _run(
            zs.scrape, city=city, query=query, max_results=max_results
        )


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
