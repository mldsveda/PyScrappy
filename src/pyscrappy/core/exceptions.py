"""PyScrappy exception hierarchy."""


class PyScrappyError(Exception):
    """Base exception for all PyScrappy errors."""


class NetworkError(PyScrappyError):
    """Raised when an HTTP request fails after retries."""


class RateLimitError(NetworkError):
    """Raised when the target site returns a rate-limit response (429)."""


class ScraperTimeoutError(PyScrappyError):
    """Raised when a scraping operation exceeds the configured timeout."""


class SelectorError(PyScrappyError):
    """Raised when a CSS/XPath selector matches nothing or is invalid."""


class BrowserNotInstalledError(PyScrappyError):
    """Raised when playwright browsers are not installed."""

    def __init__(self) -> None:
        super().__init__(
            "Playwright browsers are not installed. "
            "Install them with: pip install 'pyscrappy[browser]' && playwright install chromium"
        )
