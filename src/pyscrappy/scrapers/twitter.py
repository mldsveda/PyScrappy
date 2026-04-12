"""Twitter/X scraper.

.. note::

    Twitter/X requires authentication for most content since 2023.
    This scraper works best with the browser backend (``render_js=True``).
    Without a browser, it can only extract limited data from the initial HTML.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class TwitterScraper(BaseScraper):
    """Scrape tweets from Twitter/X.

    Usage::

        # Requires browser for full functionality
        config = ScraperConfig(rate_limit=3.0)
        with TwitterScraper(config) as scraper:
            result = scraper.scrape(
                query="python programming",
                render_js=True,
                scroll_pages=3,
                max_tweets=50,
            )
    """

    name = "twitter"

    def scrape(  # type: ignore[override]
        self,
        query: str | None = None,
        hashtag: str | None = None,
        max_tweets: int = 20,
        render_js: bool = False,
        scroll_pages: int = 0,
    ) -> ScrapeResult:
        """Scrape tweets.

        Args:
            query: Search query string.
            hashtag: Hashtag to search (without #).
            max_tweets: Maximum number of tweets to return.
            render_js: Use browser for JS rendering (recommended).
            scroll_pages: Number of scrolls for loading more tweets.

        Returns:
            ScrapeResult with tweet data.
        """
        if hashtag:
            query = f"#{hashtag}"
        if not query:
            raise ValueError("Provide either query or hashtag")

        return self._scrape_search(query, max_tweets, render_js, scroll_pages)

    def _scrape_search(
        self, query: str, max_tweets: int, render_js: bool, scroll_pages: int
    ) -> ScrapeResult:
        from urllib.parse import quote_plus

        url = f"https://x.com/search?q={quote_plus(query)}&src=typed_query&f=live"
        errors: list[ScrapeError] = []

        if render_js:
            html = self.browser.get_html(
                url, wait_for="networkidle", scroll_pages=scroll_pages
            )
        else:
            html = self.http.get_html(url)

        tweets = self._extract_tweets(html, max_tweets)

        if not tweets:
            errors.append(ScrapeError(
                url=url,
                message=(
                    "No tweets extracted. Twitter/X likely requires"
                    " authentication. Use render_js=True with a"
                    " logged-in browser session."
                ),
            ))

        return ScrapeResult(
            data=tweets,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
            errors=errors,
        )

    def _extract_tweets(self, html: str, max_tweets: int) -> list[dict[str, Any]]:
        """Extract tweets from page HTML."""
        tweets: list[dict[str, Any]] = []

        # Try parsing from embedded JSON first
        json_tweets = self._extract_from_json(html, max_tweets)
        if json_tweets:
            return json_tweets

        # Fallback: parse rendered HTML
        soup = self.parse_html(html)

        for article in soup.select("article[data-testid='tweet']"):
            tweet: dict[str, Any] = {}

            # Username and display name
            user_links = article.select("a[href*='/'] span")
            if len(user_links) >= 2:
                tweet["name"] = user_links[0].get_text(strip=True)
                tweet["handle"] = user_links[1].get_text(strip=True)

            # Tweet text
            text_el = article.select_one("div[data-testid='tweetText']")
            if text_el:
                tweet["text"] = text_el.get_text(strip=True)

            # Timestamp
            time_el = article.select_one("time")
            if time_el:
                tweet["timestamp"] = time_el.get("datetime", time_el.get_text(strip=True))

            # Engagement metrics
            for testid, key in [
                ("reply", "replies"),
                ("retweet", "retweets"),
                ("like", "likes"),
            ]:
                el = article.select_one(f"button[data-testid='{testid}'] span")
                if el:
                    tweet[key] = el.get_text(strip=True)

            if tweet.get("text"):
                tweets.append(tweet)

            if len(tweets) >= max_tweets:
                break

        return tweets

    def _extract_from_json(self, html: str, max_tweets: int) -> list[dict[str, Any]]:
        """Try to extract tweets from embedded __NEXT_DATA__ or similar JSON."""
        tweets: list[dict[str, Any]] = []

        # Look for Twitter's initial state
        match = re.search(r"window\.__INITIAL_STATE__\s*=\s*({.*?});", html, re.DOTALL)
        if not match:
            return tweets

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return tweets

        # Walk through entities to find tweets
        entities = data.get("entities", {}).get("tweets", {}).get("entities", {})
        for tweet_id, tweet_data in entities.items():
            if len(tweets) >= max_tweets:
                break
            tweets.append({
                "id": tweet_id,
                "text": tweet_data.get("full_text", ""),
                "created_at": tweet_data.get("created_at", ""),
                "retweets": tweet_data.get("retweet_count"),
                "likes": tweet_data.get("favorite_count"),
            })

        return tweets
