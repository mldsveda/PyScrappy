"""Tests for pyscrappy package-level imports and __init__.py."""

import pyscrappy


class TestPackageImports:
    def test_version(self):
        # Assert a well-formed semver rather than a hardcoded value, so this
        # test doesn't need updating on every release.
        import re

        assert re.fullmatch(r"\d+\.\d+\.\d+", pyscrappy.__version__)

    def test_core_exports(self):
        assert hasattr(pyscrappy, "ScraperConfig")
        assert hasattr(pyscrappy, "ScrapeResult")

    def test_exception_exports(self):
        assert hasattr(pyscrappy, "PyScrappyError")
        assert hasattr(pyscrappy, "NetworkError")
        assert hasattr(pyscrappy, "RateLimitError")
        assert hasattr(pyscrappy, "ScraperTimeoutError")
        assert hasattr(pyscrappy, "SelectorError")
        assert hasattr(pyscrappy, "BrowserNotInstalledError")

    def test_generic_scraper_export(self):
        assert hasattr(pyscrappy, "GenericScraper")

    def test_scraper_exports(self):
        scrapers = [
            "AmazonScraper",
            "InstagramScraper",
            "TwitterScraper",
            "YouTubeScraper",
            "SoundCloudScraper",
            "SpotifyScraper",
            "ZomatoScraper",
            "IMDBScraper",
            "ImageSearchScraper",
            "LinkedInJobsScraper",
            "NewsScraper",
            "StockScraper",
            "WikipediaScraper",
        ]
        for name in scrapers:
            assert hasattr(pyscrappy, name), f"Missing export: {name}"

    def test_convenience_scrape_function(self):
        assert hasattr(pyscrappy, "scrape")
        assert callable(pyscrappy.scrape)

    def test_all_list_complete(self):
        for name in pyscrappy.__all__:
            assert hasattr(pyscrappy, name), f"{name} in __all__ but not importable"
