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
    and sending the same User-Agent being enforced) and cache the parser per-client."""
    try:
        resp = client.get(robots_url, skip_robots_check=True, headers={"User-Agent": user_agent})
        parser = _parse_robots(resp.text) if resp.status_code == 200 else _parse_robots("")
    except Exception as exc:
        logger.debug("Failed to fetch robots.txt from %s: %s", robots_url, exc)
        parser = _parse_robots("")

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
    and sending the same User-Agent being enforced) and cache the parser per-client."""
    try:
        resp = await client.get(
            robots_url, skip_robots_check=True, headers={"User-Agent": user_agent}
        )
        parser = _parse_robots(resp.text) if resp.status_code == 200 else _parse_robots("")
    except Exception as exc:
        logger.debug("Failed to fetch robots.txt from %s: %s", robots_url, exc)
        parser = _parse_robots("")

    client._robots_cache[host] = parser
    return parser
