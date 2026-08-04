"""PyScrappy — a robust, all-in-one Python web scraping toolkit.

Quick start::

    from pyscrappy import scrape, GenericScraper

    # One-liner: scrape any URL
    result = scrape("https://example.com")
    print(result.data)

    # Custom CSS selectors
    with GenericScraper() as gs:
        result = gs.scrape(
            url="https://example.com/products",
            selectors={"name": "h2.title", "price": "span.price"},
        )
        df = result.to_dataframe()

    # Site-specific scrapers
    from pyscrappy import WikipediaScraper, StockScraper, YouTubeScraper

    with WikipediaScraper() as ws:
        result = ws.scrape(query="Python (programming language)")

    with StockScraper() as ss:
        result = ss.scrape(symbol="AAPL", mode="history", period="1mo")
"""

from pyscrappy.concurrent import scrape_all, scrape_many
from pyscrappy.core.async_http import AsyncHttpClient
from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.exceptions import (
    BrowserNotInstalledError,
    NetworkError,
    PyScrappyError,
    RateLimitError,
    ScraperTimeoutError,
    SelectorError,
)
from pyscrappy.core.models import ScrapeResult
from pyscrappy.generic.scraper import GenericScraper
from pyscrappy.registry import (
    get_scraper,
    list_scrapers,
    register,
    register_scraper,
)
from pyscrappy.scrapers.amazon import AmazonScraper
from pyscrappy.scrapers.crypto import CryptoScraper
from pyscrappy.scrapers.currency import CurrencyScraper
from pyscrappy.scrapers.dictionary import DictionaryScraper
from pyscrappy.scrapers.github import GitHubScraper
from pyscrappy.scrapers.hackernews import HackerNewsScraper
from pyscrappy.scrapers.ikea import IKEAScraper
from pyscrappy.scrapers.image_search import ImageSearchScraper
from pyscrappy.scrapers.imdb import IMDBScraper
from pyscrappy.scrapers.instagram import InstagramScraper
from pyscrappy.scrapers.linkedin import LinkedInJobsScraper
from pyscrappy.scrapers.newegg import NeweggScraper
from pyscrappy.scrapers.news import NewsScraper
from pyscrappy.scrapers.openlibrary import OpenLibraryScraper
from pyscrappy.scrapers.soundcloud import SoundCloudScraper
from pyscrappy.scrapers.spotify import SpotifyScraper
from pyscrappy.scrapers.stock import StockScraper
from pyscrappy.scrapers.twitter import TwitterScraper
from pyscrappy.scrapers.ubereats import UberEatsScraper
from pyscrappy.scrapers.weather import WeatherScraper
from pyscrappy.scrapers.wikipedia import WikipediaScraper
from pyscrappy.scrapers.youtube import YouTubeScraper
from pyscrappy.scrapers.zomato import ZomatoScraper

# Register built-in scrapers so they sit in the same registry as plugins and are
# exposed uniformly to the API, MCP server, and agent. Keyed by each class's
# `name` attribute.
for _cls in (
    GenericScraper,
    AmazonScraper,
    CryptoScraper,
    CurrencyScraper,
    DictionaryScraper,
    GitHubScraper,
    HackerNewsScraper,
    IKEAScraper,
    ImageSearchScraper,
    IMDBScraper,
    InstagramScraper,
    LinkedInJobsScraper,
    NeweggScraper,
    NewsScraper,
    OpenLibraryScraper,
    SoundCloudScraper,
    SpotifyScraper,
    StockScraper,
    UberEatsScraper,
    TwitterScraper,
    WeatherScraper,
    WikipediaScraper,
    YouTubeScraper,
    ZomatoScraper,
):
    register(_cls.name, _cls)
del _cls

__version__ = "1.4.3"

__all__ = [
    # Core
    "ScraperConfig",
    "ScrapeResult",
    # Exceptions
    "PyScrappyError",
    "NetworkError",
    "RateLimitError",
    "ScraperTimeoutError",
    "SelectorError",
    "BrowserNotInstalledError",
    # Generic
    "GenericScraper",
    # E-Commerce
    "AmazonScraper",
    "CryptoScraper",
    "CurrencyScraper",
    "DictionaryScraper",
    "GitHubScraper",
    "HackerNewsScraper",
    "OpenLibraryScraper",
    "WeatherScraper",
    "NeweggScraper",
    "IKEAScraper",
    # Social Media
    "InstagramScraper",
    "TwitterScraper",
    "YouTubeScraper",
    # Music
    "SoundCloudScraper",
    "SpotifyScraper",
    # Food Delivery
    "ZomatoScraper",
    # Data / Research
    "IMDBScraper",
    "ImageSearchScraper",
    "LinkedInJobsScraper",
    "NewsScraper",
    "StockScraper",
    "UberEatsScraper",
    "WikipediaScraper",
    # Convenience
    "scrape",
    "scrape_async",
    "scrape_many",
    "scrape_all",
    "AsyncHttpClient",
    # Plugins / registry
    "BaseScraper",
    "register_scraper",
    "register",
    "get_scraper",
    "list_scrapers",
]


def scrape(
    url: str,
    selectors: "dict[str, str] | None" = None,
    max_pages: int = 1,
    render_js: bool = False,
    config: "ScraperConfig | None" = None,
) -> ScrapeResult:
    """One-liner convenience function to scrape any URL.

    Args:
        url: The URL to scrape.
        selectors: Optional CSS selectors to extract specific fields.
        max_pages: Follow pagination up to this many pages.
        render_js: Use a browser to render JavaScript.
        config: Optional scraper configuration.

    Returns:
        ScrapeResult with extracted data.

    Example::

        from pyscrappy import scrape
        result = scrape("https://example.com")
        print(result.data[0]["metadata"]["title"])
    """
    with GenericScraper(config) as gs:
        return gs.scrape(
            url=url,
            selectors=selectors,
            max_pages=max_pages,
            render_js=render_js,
        )


async def scrape_async(
    url: str,
    selectors: "dict[str, str] | None" = None,
    max_pages: int = 1,
    config: "ScraperConfig | None" = None,
) -> ScrapeResult:
    """Async one-liner to scrape any URL, for asyncio callers.

    Uses a native AsyncHttpClient (no thread pool). JS rendering is not supported
    here; use :func:`scrape` with ``render_js=True`` for browser-rendered pages.

    Example::

        import asyncio
        from pyscrappy import scrape_async
        result = asyncio.run(scrape_async("https://example.com"))
    """
    return await GenericScraper(config).scrape_async(
        url=url, selectors=selectors, max_pages=max_pages
    )
