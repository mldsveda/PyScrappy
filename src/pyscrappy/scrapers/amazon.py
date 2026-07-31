"""Amazon product search scraper.

Amazon blocks bare HTTP requests, so this scraper sends a browser-like header
set (including a ``Referer``) that gets past that from most IPs without proxies.
It works reliably for varied queries at a sane request rate; hammering the same
query rapidly can still trigger Amazon's IP-based rate limiting, so keep the
configured ``rate_limit`` in place (and caching helps with repeat queries).
"""

from __future__ import annotations

import re
from typing import Any

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class AmazonScraper(BaseScraper):
    """Search Amazon products.

    Uses a browser-like header set to get past Amazon's bot block. Reliable for
    varied queries; keep a sane ``rate_limit`` to avoid IP throttling.

    Usage::

        config = ScraperConfig(rate_limit=3.0)  # be gentle
        with AmazonScraper(config) as scraper:
            result = scraper.scrape(query="wireless headphones", max_pages=2)
    """

    name = "amazon"

    # Amazon blocks bare requests (503 / "discuss automated access" page).
    # Sending a fuller, browser-like header set — crucially including a Referer —
    # gets past that from most IPs without proxies.
    _HEADERS = {
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Referer": "https://www.google.com/",
    }

    def __init__(
        self,
        config: ScraperConfig | None = None,
        domain: str = "www.amazon.com",
    ) -> None:
        super().__init__(config)
        self._domain = domain

    def scrape(  # type: ignore[override]
        self,
        query: str,
        max_pages: int = 1,
    ) -> ScrapeResult:
        """Search for products on Amazon.

        Args:
            query: Search query string.
            max_pages: Number of result pages to scrape.

        Returns:
            ScrapeResult with product data.
        """
        products: list[dict[str, Any]] = []
        errors: list[ScrapeError] = []
        visited: list[str] = []

        for page in range(1, max_pages + 1):
            url = f"https://{self._domain}/s?k={query.replace(' ', '+')}&page={page}"
            visited.append(url)

            try:
                soup = self.fetch_and_parse(url, headers=self._HEADERS)
            except Exception as exc:
                errors.append(ScrapeError(url=url, message=str(exc)))
                break

            # Check for CAPTCHA
            if soup.find("form", action=re.compile(r"validateCaptcha")):
                errors.append(
                    ScrapeError(
                        url=url,
                        message="Amazon returned a CAPTCHA page. Try using a proxy.",
                    )
                )
                break

            page_products = self._parse_search_results(soup, url)
            if not page_products:
                break
            products.extend(page_products)

        # Nothing extracted and no error recorded: the request "succeeded" but
        # yielded no products — almost always anti-bot blocking or a layout
        # change rather than a genuinely empty result. Say so, so callers aren't
        # left with a silent empty result.
        if not products and not errors:
            errors.append(
                ScrapeError(
                    url=visited[-1] if visited else "",
                    message=(
                        "No products extracted. Amazon aggressively blocks "
                        "automated traffic — this usually means the request was "
                        "served an anti-bot page. A proxy or residential IP is "
                        "typically required."
                    ),
                )
            )

        return ScrapeResult(
            data=products,
            metadata=ScrapeMetadata(
                source_urls=visited,
                total_pages=len(visited),
                scraper=self.name,
            ),
            errors=errors,
        )

    def _parse_search_results(self, soup: Any, url: str) -> list[dict[str, Any]]:
        """Parse product cards from a search results page."""
        products: list[dict[str, Any]] = []

        for card in soup.select("[data-component-type='s-search-result']"):
            product = self._parse_product_card(card)
            if product and product.get("title"):
                products.append(product)

        return products

    def _parse_product_card(self, card: Tag) -> dict[str, Any]:
        """Extract product data from a single search result card."""
        product: dict[str, Any] = {}

        # Title
        title_el = card.select_one("h2 a span, h2 span")
        if title_el:
            product["title"] = title_el.get_text(strip=True)

        # URL
        link = card.select_one("h2 a")
        if link:
            href = str(link.get("href", ""))
            if href.startswith("/"):
                href = f"https://{self._domain}{href}"
            product["url"] = href.split("/ref=")[0]

        # Price
        price_whole = card.select_one("span.a-price-whole")
        price_frac = card.select_one("span.a-price-fraction")
        if price_whole:
            price_text = price_whole.get_text(strip=True).rstrip(".")
            if price_frac:
                price_text += "." + price_frac.get_text(strip=True)
            product["price"] = price_text

        # Original price (strikethrough)
        orig_price = card.select_one("span.a-price.a-text-price span.a-offscreen")
        if orig_price:
            product["original_price"] = orig_price.get_text(strip=True)

        # Rating
        rating_el = card.select_one("span.a-icon-alt")
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                product["rating"] = match.group(1)

        # Review count
        review_el = card.select_one("span.a-size-base.s-underline-text")
        if review_el:
            product["review_count"] = review_el.get_text(strip=True).replace(",", "")

        # Image
        img = card.select_one("img.s-image")
        if img:
            product["image"] = img.get("src", "")

        return product
