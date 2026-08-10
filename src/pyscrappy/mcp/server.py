"""MCP server exposing PyScrappy scrapers as agent tools.

Each tool wraps a PyScrappy scraper and returns a typed ``ScrapeToolResult``, so
MCP clients get a declared output schema and validated ``structuredContent``
rather than an opaque JSON string. Scrapers run in a worker thread because
PyScrappy's HTTP/browser stack is synchronous and we must not block the event
loop.
"""

from __future__ import annotations

import math
import os
from typing import Any

import anyio
from fastmcp import FastMCP
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
# Configurable via PYSCRAPPY_MCP_CACHE_TTL (seconds); falls back to 300s.
_DEFAULT_CACHE_TTL = 300.0


def _cache_ttl_from_env() -> float:
    raw = os.getenv("PYSCRAPPY_MCP_CACHE_TTL")
    if raw is None or raw.strip() == "":
        return _DEFAULT_CACHE_TTL
    try:
        ttl = float(raw)
    except ValueError:
        return _DEFAULT_CACHE_TTL
    if not math.isfinite(ttl):
        return _DEFAULT_CACHE_TTL
    return ttl


_CACHE_TTL = _cache_ttl_from_env()


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
    result: ScrapeResult = await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    return _to_result(result)


def _looks_js_rendered(result: ScrapeToolResult) -> bool:
    """Heuristic: did a static scrape come back suspiciously empty?

    Pages built with client-side JavaScript serve an almost-empty HTML shell to a
    plain HTTP fetch, so the extracted text and links are tiny. When that happens
    we hint that ``render_js=true`` (or a data endpoint) is needed.
    """
    if not result.data:
        return True
    item = result.data[0]
    text = item.get("text")
    words = text.get("word_count", 0) if isinstance(text, dict) else 0
    links = len(item.get("links", []) or [])
    tables = len(item.get("tables", []) or [])
    # Real content pages almost always clear one of these bars.
    return words < 40 and links < 5 and tables == 0


@mcp.tool()
async def scrape_url(
    url: str,
    selectors: dict[str, str] | None = None,
    max_pages: int = 1,
    render_js: bool = False,
) -> ScrapeToolResult:
    """Scrape any HTTP(S) URL and return a ScrapeToolResult whose `data` holds one object per page containing extracted text (with word_count), links, images, tables, and page metadata.

    Fetches the page over the network and parses the HTML; no data is stored or mutated. By default it makes a plain static HTTP request, so pages built client-side with JavaScript come back nearly empty. When that is detected, the returned `errors` list gets a hint to retry with render_js=true; set render_js=true to render with a headless browser instead (requires the pyscrappy[browser] extra). On empty or failed results, `data` is [], `count` is 0, and `errors` describes the problem rather than raising.

    Returns:
        ScrapeToolResult with fields: data (list of per-page dicts holding text, links, images, tables, metadata; also the keys named in `selectors` when provided), count (int number of items in data), scraper (str backend name), source_urls (list of str URLs actually fetched, one per page), and errors (list of {url, message} for non-fatal problems).

    Args:
        url: String, the page URL to scrape including scheme, e.g. "https://example.com/products". Required, no default.
        selectors: Optional dict mapping output field name to CSS selector to extract specific values into each data item, e.g. {"title": "h1", "price": ".amount"}. Default None (returns only the standard text/links/images/tables/metadata).
        max_pages: Integer, follow "next"-style pagination up to this many pages, e.g. 3. Default 1 (scrape only the given URL).
        render_js: Boolean, render JavaScript with a headless browser backend, e.g. True. Default False; allowed values True or False, and True needs the pyscrappy[browser] extra installed.

    Use this for arbitrary or unsupported sites; for common sources prefer the purpose-built siblings (scrape_wikipedia, scrape_stock, scrape_news, search_amazon, etc.), which return cleaner fields. Gotcha: if results look empty on a modern site, re-call with render_js=true or scrape the underlying data endpoint the page fetches.
    """
    result = await _run(
        _scrape_url,
        url,
        selectors=selectors,
        max_pages=max_pages,
        render_js=render_js,
        config=_config(),
    )
    if not render_js and _looks_js_rendered(result):
        result.errors.append(
            ToolError(
                url=url,
                message=(
                    "The page returned little or no content, which usually means it "
                    "is rendered client-side with JavaScript. Retry with "
                    "render_js=true (requires the pyscrappy[browser] extra), or scrape "
                    "the underlying data endpoint the page fetches instead."
                ),
            )
        )
    return result


@mcp.tool()
async def scrape_wikipedia(query: str, mode: str = "full") -> ScrapeToolResult:
    """Fetch a Wikipedia article by title or search term and return its text content.

    Makes a live network request to Wikipedia, resolving the query to the best-matching article and extracting its body. The shape of the returned text depends on `mode`: "full" returns the entire article as one string; "paragraphs" returns the article split into a list of paragraph strings; "headers" returns a list of the article's section heading strings (its table of contents). If no article matches the query, an empty result is returned (empty string for "full", empty list for "paragraphs" or "headers").

    Args:
        query: String. Article title or search term. Example: "Model Context Protocol". No default (required).
        mode: String, one of "full", "paragraphs", or "headers". Selects the return shape as described above. Example: "paragraphs". No default (required).

    Usage Guidelines:
        Use when you need the content of a known Wikipedia topic; pick "headers" first to survey structure, then "paragraphs" or "full" to pull the text. Requires network access and returns empty on a miss, so verify the query resolved before relying on the output.
    """
    with WikipediaScraper(_config()) as ws:
        return await _run(ws.scrape, query=query, mode=mode)


@mcp.tool()
async def scrape_stock(
    symbol: str,
    mode: str = "quote",
    period: str = "1mo",
    interval: str = "1d",
) -> ScrapeToolResult:
    """Fetch stock market data from Yahoo Finance and return it as a dict.

    The returned shape depends on `mode`:
        - "quote": {"symbol", "currency", "exchange", "price", "previous_close", "volume", "day_high", "day_low", "fifty_two_week_high", "fifty_two_week_low"}.
        - "history": {"symbol", "period", "rows": [{"date", "open", "high", "low", "close", "volume"}, ...]}.
        - "profile": {"symbol", "name", "currency", "exchange", "market", "timezone", "instrument_type"}.

    Behavior:
        Makes a live network request to Yahoo Finance on each call; no browser is
        required and nothing is cached or persisted. If the symbol is unknown or
        Yahoo returns no data, "rows" is an empty list (mode="history") or the
        remaining fields are None (mode="quote"/"profile"); no exception is raised
        for an empty result.

    Args:
        symbol: Ticker symbol as a string. Example: "AAPL". No default (required).
        mode: String selecting what to fetch; one of "quote", "history", "profile". Example: "quote". Default: "quote".
        period: String history window, used only when mode="history" and ignored otherwise; one of "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max". Example: "1y". Default: "1mo".
        interval: Candle size for history bars, used only when mode="history"; one of "1d", "1wk", "1mo". Example: "1wk". Default: "1d".

    Usage:
        Use for a single ticker's live quote, OHLCV history, or company profile;
        confirm the ticker is valid with list_available_scrapers or a quote lookup
        before requesting history. For non-stock assets or bulk multi-symbol
        requests, prefer the dedicated batch scraper instead.
    """
    with StockScraper(_config()) as ss:
        return await _run(ss.scrape, symbol=symbol, mode=mode, period=period, interval=interval)


@mcp.tool()
async def scrape_news(
    feed_url: str | None = None,
    site_url: str | None = None,
    article_url: str | None = None,
    max_articles: int = 50,
) -> ScrapeToolResult:
    """Fetch news articles from an RSS/Atom feed, a news site (feed auto-discovered), or a single article, and return a list of article dicts (typically: title, url, published date, author, summary, and full text where available).

    Provide exactly one of feed_url, site_url, or article_url. Fetches live content over the network at call time; results are not cached. article_url returns one article; feed_url and site_url return up to max_articles. Returns an empty list if the feed/site yields no articles or if a feed cannot be discovered or parsed.

    Args:
        feed_url: String, direct URL to an RSS/Atom feed. Example: "https://example.com/rss.xml". Default: None.
        site_url: String, news site homepage URL whose feed is auto-discovered. Example: "https://example.com". Default: None.
        article_url: String, single article URL to extract full text from. Example: "https://example.com/2026/news-story". Default: None.
        max_articles: Integer, max articles to return for feed_url or site_url; ignored for article_url. Example: 20. Default: 50.

    Use this for news content; prefer feed_url when you already know the feed, site_url when you only have the homepage, and article_url for one specific story. Call list_available_scrapers first if unsure which scraper tool fits a given source.
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
    """Search the web for images and return a list of result objects with image URLs and metadata.

    Each result is a dict with keys: "url" (direct link to the image), "thumbnail" (small preview), "title" (caption or alt text), "source_page" (page the image was found on), "width", and "height" (pixels). Every engine returns this same key set; fields a given engine can't provide are empty ("" for text, null for width/height — e.g. the Google path fills only "url", "title", and "source_page"). Results are returned in the engine's relevance order.

    Behavior:
        Issues a live query to the chosen search engine over the network, so results vary by engine, region, and time. No files are downloaded and no browser is launched; only metadata and URLs are returned. Returns an empty list if the query matches nothing or the engine returns no results.

    Args:
        query: Search terms as a string, e.g. "golden gate bridge". Required, no default.
        max_images: Integer cap on the number of results returned, e.g. 10. Defaults to 20.
        engine: String naming the search engine, one of "bing" or "google", e.g. "google". Defaults to "bing".

    Usage Guidelines:
        Use when you need image URLs or dimensions rather than a downloaded file; the returned "url" values can be fetched or passed to a downloader tool afterward. Raise max_images cautiously since larger values are slower and some engines cap the total available results.
    """
    with ImageSearchScraper(_config()) as iss:
        return await _run(iss.scrape, query=query, max_images=max_images, engine=engine)


@mcp.tool()
async def search_youtube(query: str, max_results: int = 20) -> ScrapeToolResult:
    """Search YouTube for videos matching a query and return a list of matching videos with their metadata.

    Performs a live YouTube search over the network, so results reflect current YouTube data and may vary between calls; it is read-only and has no side effects. Returns a list of video objects, each typically containing: title (str), channel (str), url/link (str) to the video, video_id (str), duration (str), view_count (int), and published/upload date (str). Returns an empty list when the query matches no videos.

    Args:
        query: The search text, as a string. Example: "model context protocol tutorial". No default (required).
        max_results: Maximum number of videos to return, as an integer. Example: 10. Default 20.

    Usage Guidelines:
        Use when you need to discover YouTube videos by keyword and get their links and metadata; the returned url is the entry point for any follow-up fetching or transcription tools. Keep max_results modest to limit latency, and note that ranking is YouTube's relevance order, not chronological.
    """
    with YouTubeScraper(_config()) as yts:
        return await _run(yts.scrape, query=query, max_results=max_results)


@mcp.tool()
async def search_linkedin_jobs(
    query: str, location: str = "", max_pages: int = 1
) -> ScrapeToolResult:
    """Search LinkedIn public job postings and return a list of matched jobs.

    Scrapes LinkedIn's public job search results over the network (no login required) and returns a list of dicts, one per posting, typically with keys: title, company, location, url, and posted_date. Returns an empty list if no postings match or the query yields no results. Live web scraping, so results reflect LinkedIn at call time and may vary between runs.

    Args:
        query: Job title or keywords as a string. Example: "machine learning engineer". No default (required).
        location: Location filter as a string; city, region, or country. Example: "London" or "United Kingdom". No default (required).
        max_pages: Number of result pages to scrape, as an integer. Each extra page adds jobs but more scraping time. Example: 2. Default: 1.

    Use this when you specifically need LinkedIn job listings; call list_available_scrapers first to confirm this scraper is available, and raise max_pages only when the first page does not return enough results.
    """
    with LinkedInJobsScraper(_config()) as ljs:
        return await _run(ljs.scrape, query=query, location=location, max_pages=max_pages)


@mcp.tool()
async def get_crypto(
    query: str | None = None, max_results: int = 20, vs_currency: str = "usd"
) -> ScrapeToolResult:
    """Fetch live cryptocurrency market data and return a list of coin records, each with fields: id, symbol, name, current price (in vs_currency), market cap, and 24h price change (percent).

    Fetches from a live crypto market data API over the network, so results reflect current prices and require internet access; no local state is read or written. When query is omitted, returns the top coins ranked by market cap. If no coins match the query, returns an empty list rather than raising.

    Args:
        query: String of comma-separated coin ids. Example: "bitcoin, ethereum". Default None (returns top coins by market cap).
        max_results: Integer maximum number of coins to return. Example: 10. Default 20.
        vs_currency: String fiat or quote currency code for prices, lowercase. Example: "usd". Allowed: any currency supported by the data source, e.g. "usd", "eur", "gbp", "jpy". Default "usd".

    Use this to look up current prices or market snapshots for specific coins or the top market. Pass coin ids (e.g. "bitcoin"), not tickers (e.g. "btc"), in query; if a lookup returns an empty list, verify the id spelling. This tool covers only crypto market data and does not scrape web pages; for general web scraping call list_available_scrapers first.
    """
    with CryptoScraper(_config()) as c:
        return await _run(c.scrape, query=query, max_results=max_results, vs_currency=vs_currency)


@mcp.tool()
async def convert_currency(
    base: str = "USD", to: str | None = None, amount: float = 1.0
) -> ScrapeToolResult:
    """Fetch live exchange rates and convert an amount from one currency to others.

    Returns a dict with the base currency, the amount converted, and a mapping of each target currency code to its converted value and unit exchange rate (e.g. {"base": "USD", "amount": 100, "results": {"EUR": {"rate": 0.92, "value": 92.0}}}).

    Behavior:
        Queries a live external exchange-rate API over the network, so results reflect current market rates and require internet access. No local state is read or written. If a requested target code is unknown or unsupported, it is omitted from "results"; if none of the targets resolve, "results" is an empty dict.

    Args:
        base: Base currency code as a 3-letter ISO 4217 string. Example: "USD". Default: "USD".
        to: Target currency codes as a comma-separated string; omit or leave empty to return rates for all available currencies. Example: "EUR,GBP". Default: None (all rates).
        amount: Amount of the base currency to convert, as a number (int or float). Example: 100. Default: 1.

    Usage:
        Use for one-off currency conversion or to pull current rates for specific pairs; pass a single code in "to" for a quick pair rate, or omit "to" to survey all rates before choosing targets. Rates are point-in-time and not suitable for historical or as-of-date lookups.
    """
    with CurrencyScraper(_config()) as c:
        return await _run(c.scrape, base=base, to=to, amount=amount)


@mcp.tool()
async def define_word(word: str) -> ScrapeToolResult:
    """Look up an English word and return its dictionary entry: definitions, part(s) of speech, and example sentences.

    Fetches from an online dictionary data source, so a network connection is required. Read-only with no side effects. If the word is not found (misspelled or not in the dictionary), returns an empty result or a not-found response rather than raising.

    Returns a structured entry for the word, typically containing the word itself, one or more part-of-speech groupings, and for each a list of definitions with optional example sentences.

    Args:
        word: The English word to define, as a string. Example: "serendipity". No default (required). Single words only; not phrases or non-English terms.

    Usage:
        Use for quick dictionary lookups of a single English word's meaning, grammar category, and usage examples. For spelling variants or unknown words, expect an empty/not-found result and verify the spelling before retrying.
    """
    with DictionaryScraper(_config()) as d:
        return await _run(d.scrape, word=word)


@mcp.tool()
async def search_github(
    query: str, max_results: int = 20, sort: str = "best-match"
) -> ScrapeToolResult:
    """Search GitHub for public repositories and return a list of repository records.

    Queries the GitHub search API over the network and returns a list of dicts, each with: name (str), owner (str), stars (int), description (str), and language (str). Results are ordered per the sort argument. Returns an empty list when no repository matches the query. Requires network access; may be subject to GitHub API rate limits.

    Args:
        query: String search expression using GitHub search syntax, including qualifiers like "language:" or "stars:". Example: "web scraping language:python". No default (required).
        max_results: Integer maximum number of repositories to return. Example: 10. Default 20.
        sort: String ordering for results; one of "best-match", "stars", "forks", or "updated". Example: "stars". Default "best-match".

    Use this to discover repositories by keyword, language, or popularity when you have a text query rather than a known repo path. Prefer "best-match" for relevance and "stars" to surface the most popular projects; narrow broad queries with GitHub qualifiers (e.g. "language:python stars:>100") to avoid rate-limited, low-signal results.
    """
    with GitHubScraper(_config()) as gh:
        return await _run(gh.scrape, query=query, max_results=max_results, sort=sort)


@mcp.tool()
async def search_hackernews(
    query: str,
    max_results: int = 20,
    by: str = "relevance",
    tags: str = "story",
) -> ScrapeToolResult:
    """Search Hacker News stories and return a list of matching story dicts, each with title, url, points, author (username), and num_comments (comment count).

    Queries the public Hacker News search index (Algolia HN API) over the network; makes no local changes. Returns an empty list when nothing matches or the query is empty.

    Args:
        query: Search terms to match against story titles and text; type: string; example: "rust async runtime"; no default (required).
        max_results: Maximum number of stories to return; type: integer; example: 10; default: 20.
        by: Result ordering; type: string; one of "relevance" or "date" ("date" sorts most recent first); example: "date"; default: "relevance".
        tags: Algolia HN tag filter; type: string; common values "story", "comment", "show_hn", "ask_hn", "poll", "job"; example: "show_hn"; default: "story".

    Use this to pull real Hacker News discussion for a topic; prefer by="date" for breaking or time-sensitive topics and by="relevance" (default) otherwise, and use the returned url and num_comments fields to link out or gauge engagement. Set tags to narrow to Show HN, Ask HN, comments, etc.
    """
    with HackerNewsScraper(_config()) as hn:
        return await _run(hn.scrape, query=query, max_results=max_results, by=by, tags=tags)


@mcp.tool()
async def search_books(query: str, max_results: int = 20) -> ScrapeToolResult:
    """Search books by title, author, or free text via the Open Library search API and return a list of matching book records.

    Queries Open Library over the network (no browser or authentication required). Returns a list of dicts, each typically containing: title (str), author_names (list of str), first_publish_year (int or None), edition_count (int), and the Open Library work key (str, e.g. "/works/OL45804W"). Fields missing upstream are omitted or None. Returns an empty list when the query matches nothing. Read-only: no local files or state are modified.

    Args:
        query: Title, author, or free-text search string. Type: string. Example: "the hobbit tolkien". Required, no default.
        max_results: Maximum number of books to return. Type: integer. Example: 10. Default: 20. Allowed: any positive integer.

    Returns:
        A list of book-record dicts as described above; empty list if there are no matches.

    Usage:
        Use for bibliographic lookups (finding editions, publication years, or authors) rather than for full text or file-based sources. For broad or misspelled queries pass a larger max_results and refine the query, since Open Library ranks loosely by relevance.
    """
    with OpenLibraryScraper(_config()) as ol:
        return await _run(ol.scrape, query=query, max_results=max_results)


@mcp.tool()
async def get_weather(location: str) -> ScrapeToolResult:
    """Fetch the current weather conditions for a named place and return a dict with keys: temperature (number, degrees Celsius), humidity (number, percent), wind_speed (number, wind speed), condition (str, e.g. "Clear", "Rain"), and location (str, the resolved place name).

    Makes a live network call to an external weather provider on each invocation, so results reflect real-time conditions and require internet access. If the location cannot be resolved or the provider returns no match, the tool returns an empty result (or an error field) rather than raising.

    Args:
        location: String naming the place to look up; a city name, optionally with a region or country to disambiguate. Example: "Tokyo, Japan". No default; this parameter is required.

    Usage Guidelines:
        Use for point-in-time current conditions only; this tool does not return forecasts or historical data. When a bare city name is ambiguous (e.g. "Springfield"), add a region or country to the string to ensure the correct match.
    """
    with WeatherScraper(_config()) as w:
        return await _run(w.scrape, location=location)


@mcp.tool()
async def search_ubereats(city: str, max_results: int = 30) -> ScrapeToolResult:
    """Search Uber Eats for restaurants delivering in a given city, returning a ScrapeToolResult envelope whose `data` is a list of restaurant objects (typically `name`, `eta`, delivery `fee`, and store `url`).

    Fetches live listings from Uber Eats over the network at call time; no API key is required. The `data` list is capped at `max_results` and each item's store `url` is the input for `get_ubereats_menu`. Alongside `data`, the envelope carries `count`, `scraper`, `source_urls`, and `errors` (non-fatal issues, each with a `url` and `message`). If the city is unrecognized or no restaurants are found, `data` is an empty list and `count` is 0.

    Args:
        city: City name to search, as a string. Example: "London". No default (required).
        max_results: Maximum number of restaurants to return, as an integer. Example: 10. Default 30.

    Use this to discover restaurants and their store URLs in a city; call it before get_ubereats_menu, which takes a store `url` from this tool's results to fetch that restaurant's full menu. For non-Uber Eats restaurant listings, use scrape_zomato instead.
    """
    with UberEatsScraper(_config()) as ue:
        return await _run(ue.scrape, city=city, max_results=max_results)


@mcp.tool()
async def get_ubereats_menu(store_url: str) -> ScrapeToolResult:
    """Fetch an Uber Eats restaurant's live menu from its store URL and return the menu items with their names, descriptions, and prices.

    Scrapes the restaurant page over the network at call time, so results reflect current listings and require internet access. Prices and availability depend on the store's configured location and hours. Returns a structured list of menu items (typically grouped by section/category); if the URL is invalid, the restaurant is unavailable, or the menu is empty, an empty result (no items) is returned rather than an error.

    Args:
        store_url: URL string of the Uber Eats store page, taken from a search_ubereats result's "url" field. Example: "https://www.ubereats.com/store/some-restaurant/abc123". No default (required).

    Usage Guidelines:
        Use after search_ubereats to turn a chosen restaurant result into its full menu; call search_ubereats first to obtain a valid store_url rather than constructing one by hand. Do not pass a plain search or homepage URL, as only a store page URL yields menu data.
    """
    with UberEatsScraper(_config()) as ue:
        return await _run(ue.get_menu, store_url)


@mcp.tool()
async def search_amazon(query: str, max_pages: int = 1) -> ScrapeToolResult:
    """Scrape Amazon search results for a query and return a list of matching products, each with its title, price, rating, and image URL.

    This performs a live network scrape of Amazon's public search results pages (no login, no API key). It has no side effects beyond outgoing HTTP requests. Results reflect Amazon's current listings and may vary by region, availability, and anti-bot throttling. Returns a list of dicts, one per product, each shaped as {"title": str, "price": str, "rating": str, "image": str}; fields that Amazon omits for a listing come back as empty strings or None. Returns an empty list when the query yields no products or when scraping is blocked.

    Args:
        query: Product search phrase, as a string. Example: "wireless headphones". No default (required).
        max_pages: Number of result pages to scrape, as an integer; higher values return more products but take longer and raise the chance of throttling. Example: 3. Default: 1.

    Usage Guidelines:
        Use to fetch a broad, current list of Amazon products for a keyword; call list_available_scrapers first if you are unsure this scraper is enabled. Prefer a small max_pages (1 to 3) to stay fast and avoid rate limiting, and treat price/rating strings as display text rather than parsed numbers.
    """
    with AmazonScraper(_config()) as az:
        return await _run(az.scrape, query=query, max_pages=max_pages)


@mcp.tool()
async def search_newegg(query: str, max_pages: int = 1) -> ScrapeToolResult:
    """Search Newegg for electronics and computer hardware, returning a list of product dicts each with title, price, product_url, image_url, rating, and item_number.

    Live-scrapes Newegg search result pages over the network; requires outbound internet access and returns an empty list if no products match or the page structure cannot be parsed. Read-only, with no side effects beyond the outbound HTTP requests.

    Args:
        query: Product search terms, given as a string. Example: "graphics card". No default (required).
        max_pages: Number of result pages to scrape, given as an integer; higher values return more products but take longer. Example: 3. Default 1.

    Usage Guidelines:
        Use for Newegg-specific electronics and PC hardware pricing or availability; for other retailers or product categories, prefer the matching sibling scraper (call list_available_scrapers first to see them). Start with the default max_pages=1 and increase only if you need more results, since each additional page adds a network round trip.
    """
    with NeweggScraper(_config()) as ne:
        return await _run(ne.scrape, query=query, max_pages=max_pages)


@mcp.tool()
async def search_ikea(
    query: str, max_results: int = 24, country: str = "us", lang: str = "en"
) -> ScrapeToolResult:
    """Search IKEA's online catalog for furniture and home products, returning a list of product dicts with fields name, type, price, and rating.

    Scrapes the IKEA store website for the given country at call time, so results require network access and reflect that store's live listings. Prices, availability, and currency are per-country and per-language. Returns an empty list if the query matches no products.

    Args:
        query: String search term for the product name or type, e.g. "desk" or "bookshelf". Required, no default.
        max_results: Integer cap on the number of products returned; e.g. 10. Default 24.
        country: String two-letter IKEA store country code that sets pricing and availability; allowed values are IKEA market codes such as "us", "gb", "de", "fr", "se". Example "gb". Default "us".
        lang: String language code for that store's listings; must be a language the chosen country's store supports, e.g. "en" for "us"/"gb" or "de" for "de". Example "de". Default "en".

    Use this to look up IKEA products and their prices for a specific market; call list_available_scrapers first to confirm the retailer is supported. Note that country and lang must be a valid pair for the target store, and prices are meaningful only in that country's currency.
    """
    with IKEAScraper(_config(), country=country, lang=lang) as ik:
        return await _run(ik.scrape, query=query, max_results=max_results)


@mcp.tool()
async def search_soundcloud(query: str, max_results: int = 20) -> ScrapeToolResult:
    """Search SoundCloud for tracks and return a list of track dicts, each with keys: title (str), artist (str), plays (int), likes (int), and url (str, the track page URL).

    Renders SoundCloud's JavaScript search results with a browser backend (Playwright/Selenium), so it requires the pyscrappy[browser] extra to be installed and launches a headless browser per call. This makes it slower and heavier than the HTTP-based search tools. Results reflect SoundCloud's live public search at call time; no login or API key is used. Returns an empty list if the query matches no tracks.

    Args:
        query: Search query string. Example: "lofi beats". No default (required).
        max_results: Maximum number of tracks to return, as an integer. Example: 10. Default 20.

    Use this when you specifically need SoundCloud track data (play/like counts and track URLs); for video results prefer search_youtube. Run list_available_scrapers first to confirm the SoundCloud browser backend is installed, since this tool fails without pyscrappy[browser].
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
    """Look up movie and TV data from IMDB via the OMDb API and return a JSON-serializable dict; a title search returns {"results": [...]} with each item holding title, year, imdb_id, and type, while an IMDB-id lookup returns a single record with full details (plot, ratings, cast, runtime, genre).

    Reads over the network from the OMDb HTTP API; no browser is needed and nothing is written or cached. Requires a free OMDb API key in the OMDB_API_KEY environment variable (get one at https://www.omdbapi.com/apikey.aspx); if it is missing the tool returns {"error": ...} explaining how to set it. When the query matches nothing, it returns an empty results list rather than raising.

    Args:
        query: String. A title to search for (e.g. "inception"), or an IMDB id starting with "tt" for a direct single-record lookup (e.g. "tt1375666"). Required, no default.
        max_pages: Integer. Number of search-result pages to fetch at 10 results per page; only applies to title searches and is ignored for IMDB-id lookups (e.g. 3). Default 1.

    Use this for on-demand film and TV metadata lookups; pass an IMDB id when you already have one to skip search and get complete details, and raise max_pages only when a broad title needs more than the first 10 matches.
    """
    with IMDBScraper(_config()) as ims:
        return await _run(ims.scrape, query=query, max_pages=max_pages)


@mcp.tool()
async def scrape_zomato(
    city: str, query: str | None = None, max_results: int = 50
) -> ScrapeToolResult:
    """Search Zomato for restaurants in a city and return a list of restaurant records.

    Scrapes Zomato's public restaurant listings over the network for the given city, optionally filtered by a cuisine or name term. Each result is a dict with fields such as name, cuisine, rating, price_for_two, address, and url; the exact keys depend on what Zomato exposes for each listing. Returns a list of these dicts ordered as Zomato ranks them, capped at max_results. Returns an empty list if the city is unknown or no restaurants match the query. Requires outbound network access; results reflect live Zomato data at call time and may vary between calls.

    Args:
        city: String city name to search within. Example: "Bangalore". Required, no default.
        query: Optional string cuisine or restaurant search term to filter results. Example: "biryani". Defaults to None (returns all restaurants for the city).
        max_results: Integer maximum number of restaurants to return. Example: 20. Defaults to 50.

    Usage:
        Call list_available_scrapers first to confirm Zomato is supported in your region. Use this when you need Zomato-sourced restaurant data specifically; for other platforms use the corresponding sibling scraper. Note that ratings and prices are point-in-time scrapes, not a stable API, so avoid caching them as authoritative.
    """
    with ZomatoScraper(_config()) as zs:
        return await _run(zs.scrape, city=city, query=query, max_results=max_results)


@mcp.tool()
async def list_available_scrapers() -> dict[str, list[str]]:
    """List every scraper registered with this server and return their names for use with scrape_with.

    Reads the server's in-process scraper registry, which includes built-in scrapers plus any installed third-party pyscrappy-* plugin packages that self-register on import. No network or browser access is performed and no state is changed. If no scrapers are registered, returns an empty list.

    Returns:
        list[str]: Scraper name identifiers (for example ["amazon", "flipkart", "youtube"]), each usable as the scraper argument to scrape_with. Empty list when none are registered.

    Usage Guidelines:
        Call this first to discover valid scraper names, then pass a returned name to scrape_with; use it to confirm a plugin registered correctly after installing a pyscrappy-* package.
    """
    from pyscrappy import list_scrapers

    return {"scrapers": sorted(list_scrapers())}


@mcp.tool()
async def scrape_with(name: str, args: dict[str, Any] | None = None) -> ScrapeToolResult:
    """Run any registered scraper (built-in or plugin) by name and return that scraper's raw scrape() output.

    This is the generic dispatch entry point for scrapers that lack a dedicated tool, notably third-party plugins. It looks up the scraper in the registry, calls its scrape() method with the given args, and returns whatever that scraper returns (typically a dict or list of records; exact shape is scraper-specific). Side effects and requirements (network requests, browser/headless rendering, auth) depend entirely on the target scraper. If name is not a registered scraper, it raises an error rather than returning empty; if the scraper runs but finds nothing, it returns that scraper's empty result (e.g. an empty list).

    Args:
        name: String, the scraper's registered name from list_available_scrapers. Example: "wikipedia". No default (required).
        args: Dict of keyword arguments forwarded to the named scraper's scrape() method; required keys depend on that scraper. Example: {"query": "Alan Turing", "lang": "en"}. No default (required).

    Use this only when no dedicated tool exists for the scraper you want; prefer a purpose-built tool when one is available. Always call list_available_scrapers first to get a valid name, since passing an unregistered name errors out.
    """
    from pyscrappy import get_scraper

    try:
        scraper_cls = get_scraper(name)
    except KeyError as exc:
        raise ValueError(str(exc)) from None

    with scraper_cls(_config()) as scraper:
        return await _run(scraper.scrape, **(args or {}))


_registered_plugin_tools: set[str] = set()


def _register_plugin_tools() -> None:
    """Register first-class MCP tools declared by plugins.

    A scraper can opt into dedicated, typed tools by setting an ``mcp_tools``
    attribute mapping ``tool_name -> method_name``. The method's signature
    becomes the tool's input schema, so an agent sees e.g. ``search_reddit`` with
    proper arguments instead of the generic ``scrape_with``. Scrapers without
    ``mcp_tools`` are unaffected and remain callable via ``scrape_with``.

    Called at server startup (and safe to call again) so plugins registered
    after import are still picked up; already-registered tools are skipped.
    """
    import inspect

    from pyscrappy import list_scrapers

    for scraper_name, scraper_cls in list_scrapers().items():
        mcp_tools = getattr(scraper_cls, "mcp_tools", None)
        if not mcp_tools:
            continue

        for tool_name, method_name in dict(mcp_tools).items():
            if tool_name in _registered_plugin_tools:
                continue
            method = getattr(scraper_cls, method_name, None)
            if method is None:
                continue

            # Bind loop vars per iteration.
            def _make(cls=scraper_cls, m_name=method_name):
                async def _tool(**kwargs: Any) -> ScrapeToolResult:
                    with cls(_config()) as scraper:
                        return await _run(getattr(scraper, m_name), **kwargs)

                # Expose the scraper method's signature (minus self) so FastMCP
                # derives a typed input schema from it. The return annotation is
                # forced to ScrapeToolResult — what _tool actually returns —
                # otherwise FastMCP validates against the method's own return
                # type (ScrapeResult) and rejects the result.
                sig = inspect.signature(method)
                params = [p for p in sig.parameters.values() if p.name != "self"]
                _tool.__signature__ = sig.replace(
                    parameters=params, return_annotation=ScrapeToolResult
                )
                # fastmcp derives the input schema from __annotations__ (not
                # __signature__), so keep them in sync — otherwise pydantic looks
                # up a signature param that's absent from annotations and raises
                # KeyError. The real _tool takes **kwargs, so we rewrite its
                # annotations to the scraper method's typed params + return type.
                _tool.__annotations__ = {
                    p.name: (p.annotation if p.annotation is not inspect.Parameter.empty else Any)
                    for p in params
                }
                _tool.__annotations__["return"] = ScrapeToolResult
                return _tool

            fn = _make()
            fn.__name__ = tool_name
            fn.__doc__ = (method.__doc__ or f"Run the {scraper_name} scraper.").strip()
            # fastmcp derives the tool name and description from fn.__name__ /
            # fn.__doc__ (set just above), so no explicit name/description kwargs.
            mcp.add_tool(fn)
            _registered_plugin_tools.add(tool_name)


def main() -> None:
    """Console-script entry point.

    Runs over stdio by default (for local MCP clients like Claude Desktop). Pass
    ``--http`` to expose the server over Streamable HTTP instead, so it can be
    self-hosted as a remote MCP endpoint.
    """
    import argparse

    # Register plugin-declared tools now that all installed plugins are known.
    _register_plugin_tools()

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
        # fastmcp 3.x takes host/port as run() kwargs (there's no mcp.settings).
        mcp.run(
            transport="sse" if args.sse else "streamable-http",
            host=args.host,
            port=args.port,
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
