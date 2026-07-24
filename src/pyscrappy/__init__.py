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
from pyscrappy.scrapers.alibaba import AlibabaScraper
from pyscrappy.scrapers.amazon import AmazonScraper
from pyscrappy.scrapers.flipkart import FlipkartScraper
from pyscrappy.scrapers.image_search import ImageSearchScraper
from pyscrappy.scrapers.imdb import IMDBScraper
from pyscrappy.scrapers.instagram import InstagramScraper
from pyscrappy.scrapers.linkedin import LinkedInJobsScraper
from pyscrappy.scrapers.news import NewsScraper
from pyscrappy.scrapers.snapdeal import SnapdealScraper
from pyscrappy.scrapers.soundcloud import SoundCloudScraper
from pyscrappy.scrapers.spotify import SpotifyScraper
from pyscrappy.scrapers.stock import StockScraper
from pyscrappy.scrapers.swiggy import SwiggyScraper
from pyscrappy.scrapers.twitter import TwitterScraper
from pyscrappy.scrapers.wikipedia import WikipediaScraper
from pyscrappy.scrapers.youtube import YouTubeScraper
from pyscrappy.scrapers.zomato import ZomatoScraper

__version__ = "1.1.0"

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
    "AlibabaScraper",
    "AmazonScraper",
    "FlipkartScraper",
    "SnapdealScraper",
    # Social Media
    "InstagramScraper",
    "TwitterScraper",
    "YouTubeScraper",
    # Music
    "SoundCloudScraper",
    "SpotifyScraper",
    # Food Delivery
    "SwiggyScraper",
    "ZomatoScraper",
    # Data / Research
    "IMDBScraper",
    "ImageSearchScraper",
    "LinkedInJobsScraper",
    "NewsScraper",
    "StockScraper",
    "WikipediaScraper",
    # Convenience
    "scrape",
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
