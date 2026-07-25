"""Scraping-API service integration.

Some sites (Amazon under load, eBay, Alibaba, Instagram, ...) block direct
requests and can only be reached reliably through a scraping-API service that
handles proxies and anti-bot challenges. This module maps a target URL into a
request to such a service, given a ``scraper_api`` config.

Supported providers (all have free tiers):

* ``scraperapi``  - https://www.scraperapi.com
* ``scrapeops``   - https://scrapeops.io
* ``scrapingbee`` - https://www.scrapingbee.com

Config shape::

    ScraperConfig(scraper_api={"provider": "scraperapi", "api_key": "KEY",
                               "render_js": True})  # render_js optional
"""

from __future__ import annotations

from typing import Any

# endpoint + how each provider names its parameters
_PROVIDERS: dict[str, dict[str, str]] = {
    "scraperapi": {
        "endpoint": "https://api.scraperapi.com/",
        "url_param": "url",
        "key_param": "api_key",
        "render_param": "render",
    },
    "scrapeops": {
        "endpoint": "https://proxy.scrapeops.io/v1/",
        "url_param": "url",
        "key_param": "api_key",
        "render_param": "render_js",
    },
    "scrapingbee": {
        "endpoint": "https://app.scrapingbee.com/api/v1/",
        "url_param": "url",
        "key_param": "api_key",
        "render_param": "render_js",
    },
}


def is_configured(scraper_api: dict[str, str] | None) -> bool:
    """True if a usable scraper-API config is present."""
    return bool(scraper_api and scraper_api.get("provider") and scraper_api.get("api_key"))


def build_request(target_url: str, scraper_api: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Map a target URL into a (service_endpoint, params) request.

    Args:
        target_url: The URL you actually want to scrape.
        scraper_api: The ``ScraperConfig.scraper_api`` dict.

    Returns:
        ``(endpoint, params)`` to pass to an HTTP GET.

    Raises:
        ValueError: If the provider is unknown or the api_key is missing.
    """
    provider = scraper_api.get("provider", "")
    api_key = scraper_api.get("api_key")
    spec = _PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(
            f"Unknown scraper_api provider {provider!r}. "
            f"Supported: {', '.join(sorted(_PROVIDERS))}."
        )
    if not api_key:
        raise ValueError("scraper_api.api_key is required.")

    params = {
        spec["key_param"]: api_key,
        spec["url_param"]: target_url,
    }
    if scraper_api.get("render_js"):
        params[spec["render_param"]] = "true"

    return spec["endpoint"], params
