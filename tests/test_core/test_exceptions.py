"""Tests for pyscrappy.core.exceptions."""

import pytest

from pyscrappy.core.exceptions import (
    BrowserNotInstalledError,
    NetworkError,
    PyScrappyError,
    RateLimitError,
    ScraperTimeoutError,
    SelectorError,
)


class TestExceptionHierarchy:
    def test_pyscrappy_error_is_base(self):
        assert issubclass(PyScrappyError, Exception)

    def test_network_error_inherits_pyscrappy_error(self):
        assert issubclass(NetworkError, PyScrappyError)

    def test_rate_limit_error_inherits_network_error(self):
        assert issubclass(RateLimitError, NetworkError)
        assert issubclass(RateLimitError, PyScrappyError)

    def test_scraper_timeout_error_inherits_pyscrappy_error(self):
        assert issubclass(ScraperTimeoutError, PyScrappyError)

    def test_selector_error_inherits_pyscrappy_error(self):
        assert issubclass(SelectorError, PyScrappyError)

    def test_browser_not_installed_error_inherits_pyscrappy_error(self):
        assert issubclass(BrowserNotInstalledError, PyScrappyError)


class TestBrowserNotInstalledError:
    def test_default_message(self):
        err = BrowserNotInstalledError()
        assert "Playwright browsers are not installed" in str(err)
        assert "pip install 'pyscrappy[browser]'" in str(err)
        assert "playwright install chromium" in str(err)


class TestExceptionsCanBeCaught:
    def test_catch_network_error_as_pyscrappy_error(self):
        with pytest.raises(PyScrappyError):
            raise NetworkError("connection failed")

    def test_catch_rate_limit_as_network_error(self):
        with pytest.raises(NetworkError):
            raise RateLimitError("429 too many requests")

    def test_catch_rate_limit_as_pyscrappy_error(self):
        with pytest.raises(PyScrappyError):
            raise RateLimitError("429")

    def test_network_error_message(self):
        err = NetworkError("HTTP 500 from example.com")
        assert str(err) == "HTTP 500 from example.com"
