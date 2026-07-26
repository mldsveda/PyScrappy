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
    CryptoScraper,
    CurrencyScraper,
    DictionaryScraper,
    GitHubScraper,
    HackerNewsScraper,
    IKEAScraper,
    ImageSearchScraper,
    IMDBScraper,
    LinkedInJobsScraper,
    NeweggScraper,
    NewsScraper,
    OpenLibraryScraper,
    ScrapeResult,
    SoundCloudScraper,
    StockScraper,
    UberEatsScraper,
    WeatherScraper,
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
async def get_crypto(
    query: str | None = None, max_results: int = 20, vs_currency: str = "usd"
) -> ScrapeToolResult:
    """Get cryptocurrency market data (price, market cap, 24h change).

    Args:
        query: Comma-separated coins (e.g. "bitcoin, ethereum"). Omit for top coins.
        max_results: Max coins to return (default 20).
        vs_currency: Fiat currency for prices, e.g. "usd", "eur" (default "usd").
    """
    with CryptoScraper(_config()) as c:
        return await _run(
            c.scrape, query=query, max_results=max_results, vs_currency=vs_currency
        )


@mcp.tool()
async def convert_currency(
    base: str = "USD", to: str | None = None, amount: float = 1.0
) -> ScrapeToolResult:
    """Get currency exchange rates and convert an amount.

    Args:
        base: Base currency code, e.g. "USD".
        to: Comma-separated target codes (e.g. "EUR,GBP"). Omit for all rates.
        amount: Amount of base currency to convert (default 1).
    """
    with CurrencyScraper(_config()) as c:
        return await _run(c.scrape, base=base, to=to, amount=amount)


@mcp.tool()
async def define_word(word: str) -> ScrapeToolResult:
    """Look up a word's definitions, part of speech, and examples (English).

    Args:
        word: The word to define.
    """
    with DictionaryScraper(_config()) as d:
        return await _run(d.scrape, word=word)


@mcp.tool()
async def search_github(
    query: str, max_results: int = 20, sort: str = "best-match"
) -> ScrapeToolResult:
    """Search GitHub repositories (name, owner, stars, description, language).

    Args:
        query: Search query, e.g. "web scraping language:python".
        max_results: Max repositories to return (default 20).
        sort: "best-match" (default), "stars", "forks", or "updated".
    """
    with GitHubScraper(_config()) as gh:
        return await _run(gh.scrape, query=query, max_results=max_results, sort=sort)


@mcp.tool()
async def search_hackernews(
    query: str, max_results: int = 20, by: str = "relevance"
) -> ScrapeToolResult:
    """Search Hacker News stories (title, url, points, author, comments).

    Args:
        query: Search query.
        max_results: Max stories to return (default 20).
        by: "relevance" (default) or "date" (most recent first).
    """
    with HackerNewsScraper(_config()) as hn:
        return await _run(hn.scrape, query=query, max_results=max_results, by=by)


@mcp.tool()
async def search_books(query: str, max_results: int = 20) -> ScrapeToolResult:
    """Search books via Open Library (title, author, year, editions).

    Args:
        query: Title, author, or free-text search.
        max_results: Max books to return (default 20).
    """
    with OpenLibraryScraper(_config()) as ol:
        return await _run(ol.scrape, query=query, max_results=max_results)


@mcp.tool()
async def get_weather(location: str) -> ScrapeToolResult:
    """Get current weather for a place (temperature, humidity, wind, condition).

    Args:
        location: Place name, e.g. "London" or "Tokyo, Japan".
    """
    with WeatherScraper(_config()) as w:
        return await _run(w.scrape, location=location)


@mcp.tool()
async def search_ubereats(city: str, max_results: int = 30) -> ScrapeToolResult:
    """List Uber Eats restaurants delivering in a city (name, ETA, fee, url).

    Args:
        city: City name, e.g. "London".
        max_results: Maximum restaurants to return (default 30).
    """
    with UberEatsScraper(_config()) as ue:
        return await _run(ue.scrape, city=city, max_results=max_results)


@mcp.tool()
async def get_ubereats_menu(store_url: str) -> ScrapeToolResult:
    """Get an Uber Eats restaurant's menu (items, prices) from its store URL.

    Args:
        store_url: A store URL from a search_ubereats result's "url" field.
    """
    with UberEatsScraper(_config()) as ue:
        return await _run(ue.get_menu, store_url)


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
async def search_ikea(
    query: str, max_results: int = 24, country: str = "us", lang: str = "en"
) -> ScrapeToolResult:
    """Search IKEA furniture and home products (name, type, price, rating).

    Prices and availability are per-country: pass the country's IKEA store code.

    Args:
        query: Product search query, e.g. "desk" or "bookshelf".
        max_results: Maximum number of products to return (default 24).
        country: IKEA store country code, e.g. "us", "gb", "de" (default "us").
        lang: Language code for that store, e.g. "en", "de" (default "en").
    """
    with IKEAScraper(_config(), country=country, lang=lang) as ik:
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
    """Console-script entry point.

    Runs over stdio by default (for local MCP clients like Claude Desktop). Pass
    ``--http`` to expose the server over Streamable HTTP instead, so it can be
    self-hosted as a remote MCP endpoint.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="pyscrappy-mcp",
        description="PyScrappy MCP server. Runs over stdio by default; use --http "
        "to serve over HTTP for self-hosting as a remote MCP server.",
    )
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument(
        "--http",
        action="store_true",
        help="Serve over Streamable HTTP instead of stdio.",
    )
    transport.add_argument(
        "--sse",
        action="store_true",
        help="Serve over the legacy SSE transport instead of stdio.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind when serving over HTTP/SSE (default: 127.0.0.1). "
        "Use 0.0.0.0 to accept remote connections.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind when serving over HTTP/SSE (default: 8000).",
    )
    args = parser.parse_args()

    if args.http or args.sse:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse" if args.sse else "streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
