"""Robots.txt fetching, caching, and politeness enforcement."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from pyscrappy.core.exceptions import RobotsDisallowedError

if TYPE_CHECKING:
    import httpx

    from pyscrappy.core.async_http import AsyncHttpClient
    from pyscrappy.core.http import HttpClient

logger = logging.getLogger("pyscrappy.robots")

# Per-host cache of (RobotFileParser, crawl_delay)
_ROBOTS_CACHE: dict[str, tuple[RobotFileParser, float | None]] = {}
_ROBOTS_LOCK = threading.Lock()
_ASYNC_ROBOTS_LOCK = asyncio.Lock()


def get_host_and_robots_url(url: str) -> tuple[str, str]:
    """Extract (host, robots_url) for a given target URL."""
    parsed = urlparse(url)
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or parsed.path.split("/")[0]
    robots_url = f"{scheme}://{netloc}/robots.txt"
    return netloc.lower(), robots_url


def _parse_robots(text: str, user_agent: str) -> tuple[RobotFileParser, float | None]:
    """Parse robots.txt content and extract crawl_delay for the user_agent."""
    parser = RobotFileParser()
    parser.parse(text.splitlines())

    # Get crawl_delay if present
    delay: float | None = None
    try:
        raw_delay = parser.crawl_delay(user_agent)
        if raw_delay is not None:
            delay = float(raw_delay)
    except Exception:
        delay = None

    return parser, delay


def check_robots_sync(client: HttpClient, url: str) -> float | None:
    """Sync check: fetch and parse robots.txt for URL host if needed, evaluate
    permissions, and return any Crawl-delay.

    Raises:
        RobotsDisallowedError: If the URL is disallowed for the client's user-agent.
    """
    host, robots_url = get_host_and_robots_url(url)
    user_agent = client._get_current_user_agent()

    with _ROBOTS_LOCK:
        if host in _ROBOTS_CACHE:
            parser, delay = _ROBOTS_CACHE[host]
        else:
            parser, delay = _fetch_and_cache_sync(client, host, robots_url, user_agent)

    if not parser.can_fetch(user_agent, url):
        raise RobotsDisallowedError(
            f"URL '{url}' is disallowed for user-agent '{user_agent}' by robots.txt at {robots_url}"
        )

    return delay


def _fetch_and_cache_sync(
    client: HttpClient, host: str, robots_url: str, user_agent: str
) -> tuple[RobotFileParser, float | None]:
    """Fetch robots.txt via sync client and store in cache."""
    parser = RobotFileParser()

    # Prevent recursive obey_robots check when fetching robots.txt itself
    orig_obey = client.config.obey_robots
    client.config.obey_robots = False
    try:
        resp = client.get(robots_url)
        if resp.status_code == 200:
            parser, delay = _parse_robots(resp.text, user_agent)
        else:
            parser.parse([])
            delay = None
    except Exception as exc:
        logger.debug("Failed to fetch robots.txt from %s: %s", robots_url, exc)
        parser.parse([])
        delay = None
    finally:
        client.config.obey_robots = orig_obey

    _ROBOTS_CACHE[host] = (parser, delay)
    return parser, delay


async def check_robots_async(client: AsyncHttpClient, url: str) -> float | None:
    """Async check: fetch and parse robots.txt for URL host if needed, evaluate
    permissions, and return any Crawl-delay.

    Raises:
        RobotsDisallowedError: If the URL is disallowed for the client's user-agent.
    """
    host, robots_url = get_host_and_robots_url(url)
    user_agent = client._get_current_user_agent()

    async with _ASYNC_ROBOTS_LOCK:
        if host in _ROBOTS_CACHE:
            parser, delay = _ROBOTS_CACHE[host]
        else:
            parser, delay = await _fetch_and_cache_async(client, host, robots_url, user_agent)

    if not parser.can_fetch(user_agent, url):
        raise RobotsDisallowedError(
            f"URL '{url}' is disallowed for user-agent '{user_agent}' by robots.txt at {robots_url}"
        )

    return delay


async def _fetch_and_cache_async(
    client: AsyncHttpClient, host: str, robots_url: str, user_agent: str
) -> tuple[RobotFileParser, float | None]:
    """Fetch robots.txt via async client and store in cache."""
    parser = RobotFileParser()

    orig_obey = client.config.obey_robots
    client.config.obey_robots = False
    try:
        resp = await client.get(robots_url)
        if resp.status_code == 200:
            parser, delay = _parse_robots(resp.text, user_agent)
        else:
            parser.parse([])
            delay = None
    except Exception as exc:
        logger.debug("Failed to fetch robots.txt from %s: %s", robots_url, exc)
        parser.parse([])
        delay = None
    finally:
        client.config.obey_robots = orig_obey

    with _ROBOTS_LOCK:
        _ROBOTS_CACHE[host] = (parser, delay)
    return parser, delay
