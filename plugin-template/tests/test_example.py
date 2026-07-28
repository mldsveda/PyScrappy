"""Test that the plugin is registered and usable through PyScrappy.

Run with `pytest` after `pip install -e .`.
"""

from pyscrappy import get_scraper, list_scrapers

from pyscrappy_example import ExampleScraper


def test_plugin_is_discovered():
    # After install, PyScrappy finds the scraper via the entry point.
    assert "example" in list_scrapers()
    assert get_scraper("example") is ExampleScraper


def test_scrape_returns_result():
    result = ExampleScraper().scrape()
    assert result.data
    assert "title" in result.data[0]
    assert result.metadata.scraper == "example"
