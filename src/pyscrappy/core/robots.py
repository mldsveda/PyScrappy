"""Robots.txt fetching, caching, and politeness enforcement."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from pyscrappy.core.exceptions import RobotsDisallowedError

if TYPE_CHECKING:
    from pyscrappy.core.async_http import AsyncHttpClient
    from pyscrappy.core.http import HttpClient

logger = logging.getLogger("pyscrappy.robots")


def get_host_and_robots_url(url: str) -> tuple[str, str]:
    """Extract (host, robots_url) for a given target URL."""
    parsed = urlparse(url)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or parsed.path.split("/")[0]
    robots_url = f"{scheme}://{netloc}/robots.txt"
    return netloc.lower(), robots_url


def _parse_robots(text: str) -> RobotFileParser:
    """Parse robots.txt content into a RobotFileParser."""
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    return parser


def _disallow_all() -> RobotFileParser:
    """A parser that forbids everything, for transient robots.txt failures."""
    return _parse_robots("User-agent: *\nDisallow: /")


def _parser_for_response(status_code: int, text: str) -> tuple[RobotFileParser, bool]:
    """Decide the parser for a robots.txt HTTP response, and whether it may be
    cached, following RFC 9309 / Googlebot conventions:

    - 2xx: use the returned rules (cacheable).
    - 4xx (e.g. 404/410 "no robots.txt"): allow-all (cacheable).
    - 5xx: disallow-all, and *not* cacheable, because a server error is transient
      and a later request should re-fetch rather than reuse a temporary block.

    Returns ``(parser, cacheable)``.
    """
    if 200 <= status_code < 300:
        return _parse_robots(text), True
    if 400 <= status_code < 500:
        return _parse_robots(""), True
    # 5xx (and any other unexpected status): fail closed, don't cache.
    return _disallow_all(), False


def _crawl_delay_for(parser: RobotFileParser, user_agent: str) -> float | None:
    """Crawl-delay this parser advertises for ``user_agent`` (None if absent).

    Computed per request rather than cached as a single value, since robots.txt
    can set different Crawl-delay values for different User-Agent groups and the
    client may rotate UAs.
    """
    try:
        raw_delay = parser.crawl_delay(user_agent)
        return float(raw_delay) if raw_delay is not None else None
    except Exception:
        return None


def check_robots_sync(client: HttpClient, url: str, user_agent: str) -> float | None:
    """Sync check: fetch and parse robots.txt for URL host if needed, evaluate
    permissions, and return the Crawl-delay for ``user_agent`` using the per-client
    cache.

    Raises:
        RobotsDisallowedError: If the URL is disallowed for the client's user-agent.
    """
    host, robots_url = get_host_and_robots_url(url)

    parser = client._robots_cache.get(host)
    if parser is None:
        parser = _fetch_and_cache_sync(client, host, robots_url, user_agent)

    if not parser.can_fetch(user_agent, url):
        raise RobotsDisallowedError(
            f"URL '{url}' is disallowed for user-agent '{user_agent}' by robots.txt at {robots_url}"
        )

    return _crawl_delay_for(parser, user_agent)


def _fetch_and_cache_sync(
    client: HttpClient, host: str, robots_url: str, user_agent: str
) -> RobotFileParser:
    """Fetch robots.txt via the sync client (skipping the robots check recursively,
    and sending the same User-Agent being enforced) and cache the parser per-client.

    Transient failures (5xx or a network error) fail closed with a disallow-all
    parser that is *not* cached, so the next request re-fetches instead of reusing
    a temporary block."""
    # get_raw (not get) so a non-200 returns its status code instead of raising,
    # letting us tell 4xx (allow-all) apart from 5xx (fail closed). It performs a
    # bare fetch with no robots check, so there is no recursion.
    try:
        resp = client.get_raw(robots_url, headers={"User-Agent": user_agent})
        parser, cacheable = _parser_for_response(resp.status_code, resp.text)
    except Exception as exc:
        logger.debug("Failed to fetch robots.txt from %s: %s", robots_url, exc)
        parser, cacheable = _disallow_all(), False

    if cacheable:
        client._robots_cache[host] = parser
    return parser


async def check_robots_async(client: AsyncHttpClient, url: str, user_agent: str) -> float | None:
    """Async check: fetch and parse robots.txt for URL host if needed, evaluate
    permissions, and return the Crawl-delay for ``user_agent`` using the per-client
    cache.

    Raises:
        RobotsDisallowedError: If the URL is disallowed for the client's user-agent.
    """
    host, robots_url = get_host_and_robots_url(url)

    parser = client._robots_cache.get(host)
    if parser is None:
        parser = await _fetch_and_cache_async(client, host, robots_url, user_agent)

    if not parser.can_fetch(user_agent, url):
        raise RobotsDisallowedError(
            f"URL '{url}' is disallowed for user-agent '{user_agent}' by robots.txt at {robots_url}"
        )

    return _crawl_delay_for(parser, user_agent)


async def _fetch_and_cache_async(
    client: AsyncHttpClient, host: str, robots_url: str, user_agent: str
) -> RobotFileParser:
    """Fetch robots.txt via the async client (skipping the robots check recursively,
    and sending the same User-Agent being enforced) and cache the parser per-client.

    Transient failures (5xx or a network error) fail closed with a disallow-all
    parser that is *not* cached, so the next request re-fetches instead of reusing
    a temporary block."""
    # get_raw (not get) so a non-200 returns its status code instead of raising,
    # letting us tell 4xx (allow-all) apart from 5xx (fail closed). It performs a
    # bare fetch with no robots check, so there is no recursion.
    try:
        resp = await client.get_raw(robots_url, headers={"User-Agent": user_agent})
        parser, cacheable = _parser_for_response(resp.status_code, resp.text)
    except Exception as exc:
        logger.debug("Failed to fetch robots.txt from %s: %s", robots_url, exc)
        parser, cacheable = _disallow_all(), False

    if cacheable:
        client._robots_cache[host] = parser
    return parser
