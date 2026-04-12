"""News scraper — extract articles from RSS feeds and web pages."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

from bs4 import Tag

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.config import ScraperConfig
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class NewsScraper(BaseScraper):
    """Scrape news articles from RSS/Atom feeds or news websites.

    Usage::

        with NewsScraper() as scraper:
            # From an RSS feed
            result = scraper.scrape(feed_url="https://rss.nytimes.com/services/xml/rss/nyt/World.xml")

            # From a news site (auto-discovers RSS)
            result = scraper.scrape(site_url="https://www.bbc.com/news")

            # Extract full article text from a single URL
            result = scraper.scrape(article_url="https://example.com/article/123")
    """

    name = "news"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    def scrape(  # type: ignore[override]
        self,
        feed_url: str | None = None,
        site_url: str | None = None,
        article_url: str | None = None,
        max_articles: int = 50,
    ) -> ScrapeResult:
        """Scrape news articles.

        Args:
            feed_url: Direct URL to an RSS or Atom feed.
            site_url: URL of a news website — RSS feed will be auto-discovered.
            article_url: URL of a single article to extract full text from.
            max_articles: Maximum number of articles to return from feeds.

        Returns:
            ScrapeResult with article data (title, link, published, summary).
        """
        if article_url:
            return self._scrape_article(article_url)
        if feed_url:
            return self._scrape_feed(feed_url, max_articles)
        if site_url:
            return self._scrape_site(site_url, max_articles)
        raise ValueError("Provide at least one of: feed_url, site_url, or article_url")

    def _scrape_feed(self, url: str, max_articles: int) -> ScrapeResult:
        """Parse an RSS or Atom feed."""
        xml_text = self.http.get_html(url)
        articles = self._parse_feed_xml(xml_text, max_articles)

        return ScrapeResult(
            data=articles,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _scrape_site(self, url: str, max_articles: int) -> ScrapeResult:
        """Auto-discover an RSS feed from a website, then parse it."""
        html = self.http.get_html(url)
        soup = self.parse_html(html)
        errors: list[ScrapeError] = []

        feed_url = self._discover_feed(soup, url)
        if feed_url:
            return self._scrape_feed(feed_url, max_articles)

        # Fallback: extract article links from the page directly
        self.logger.info("No RSS feed found, extracting article links from HTML")
        articles = self._extract_article_links(soup, url)
        if not articles:
            errors.append(ScrapeError(url=url, message="No RSS feed or article links found"))

        return ScrapeResult(
            data=articles[:max_articles],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _scrape_article(self, url: str) -> ScrapeResult:
        """Extract the full text of a single news article."""
        soup = self.fetch_and_parse(url)

        article: dict[str, Any] = {"url": url}

        # Title
        title_el = soup.find("title")
        if title_el:
            article["title"] = title_el.get_text(strip=True)

        og_title = soup.find("meta", property="og:title")
        if og_title and isinstance(og_title, Tag):
            article["title"] = og_title.get("content", article.get("title", ""))

        # Published date
        for attr in ("article:published_time", "datePublished", "date"):
            meta = soup.find("meta", attrs={"property": attr}) or soup.find(
                "meta", attrs={"name": attr}
            )
            if meta and isinstance(meta, Tag):
                article["published"] = meta.get("content", "")
                break
        time_el = soup.find("time")
        if time_el and isinstance(time_el, Tag) and "published" not in article:
            article["published"] = time_el.get("datetime", time_el.get_text(strip=True))

        # Author
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and isinstance(author_meta, Tag):
            article["author"] = author_meta.get("content", "")

        # Main content
        main = soup.find("article") or soup.find("main") or soup.find(role="main")
        if main and isinstance(main, Tag):
            paragraphs = [
                p.get_text(strip=True) for p in main.find_all("p")
                if len(p.get_text(strip=True)) > 30
            ]
        else:
            paragraphs = [
                p.get_text(strip=True) for p in soup.find_all("p")
                if len(p.get_text(strip=True)) > 50
            ]

        article["text"] = "\n\n".join(paragraphs)
        article["word_count"] = len(article["text"].split())

        return ScrapeResult(
            data=[article],
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )

    def _parse_feed_xml(self, xml_text: str, max_articles: int) -> list[dict[str, Any]]:
        """Parse RSS 2.0 or Atom XML into a list of articles."""
        articles: list[dict[str, Any]] = []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return articles

        # Namespace handling for Atom

        # RSS 2.0: <channel><item>
        for item in root.iter("item"):
            article = {
                "title": self._xml_text(item, "title"),
                "link": self._xml_text(item, "link"),
                "published": self._xml_text(item, "pubDate"),
                "summary": self._clean_html(self._xml_text(item, "description")),
            }
            if article["title"]:
                articles.append(article)
            if len(articles) >= max_articles:
                return articles

        # Atom: <feed><entry>
        if not articles:
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                article = {
                    "title": self._xml_text(entry, "{http://www.w3.org/2005/Atom}title"),
                    "link": link_el.get("href", "") if link_el is not None else "",
                    "published": self._xml_text(entry, "{http://www.w3.org/2005/Atom}updated"),
                    "summary": self._clean_html(
                        self._xml_text(entry, "{http://www.w3.org/2005/Atom}summary")
                    ),
                }
                if article["title"]:
                    articles.append(article)
                if len(articles) >= max_articles:
                    return articles

        return articles

    def _discover_feed(self, soup: Any, base_url: str) -> str | None:
        """Find RSS/Atom feed link in page <head>."""
        for link in soup.find_all("link", type=re.compile(r"(rss|atom|xml)")):
            href = link.get("href")
            if href:
                return urljoin(base_url, str(href))
        return None

    def _extract_article_links(self, soup: Any, base_url: str) -> list[dict[str, Any]]:
        """Fallback: extract headline links that look like articles."""
        articles: list[dict[str, Any]] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            text = a.get_text(strip=True)
            if not text or len(text) < 20:
                continue

            abs_url = urljoin(base_url, href)
            if abs_url in seen:
                continue

            # Heuristic: article URLs tend to have slugs
            if re.search(r"/\d{4}/|/article|/story|/news/", href):
                seen.add(abs_url)
                articles.append({"title": text, "link": abs_url})

        return articles

    @staticmethod
    def _xml_text(element: Any, tag: str) -> str:
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    @staticmethod
    def _clean_html(text: str) -> str:
        """Strip HTML tags from RSS description content."""
        return re.sub(r"<[^>]+>", "", text).strip()
