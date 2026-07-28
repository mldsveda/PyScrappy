"""Tests for first-class MCP tools declared by plugins via `mcp_tools`."""

import pytest

from pyscrappy import BaseScraper, register_scraper
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult


@register_scraper("reddit_test")
class _RedditTest(BaseScraper):
    mcp_tools = {"search_reddit_test": "scrape"}

    def scrape(self, subreddit: str, sort: str = "hot") -> ScrapeResult:
        return ScrapeResult(
            data=[{"sub": subreddit, "sort": sort}],
            metadata=ScrapeMetadata(scraper="reddit_test"),
        )


@register_scraper("plain_test")
class _PlainTest(BaseScraper):
    # No mcp_tools -> should NOT get a dedicated tool, only scrape_with.
    def scrape(self, q: str) -> ScrapeResult:
        return ScrapeResult(data=[], metadata=ScrapeMetadata(scraper="plain_test"))


def _server():
    import pyscrappy.mcp.server as server

    # Registration now happens at startup, not import; trigger it here so the
    # plugins declared above are picked up regardless of test import order.
    server._register_plugin_tools()
    return server


@pytest.mark.anyio
async def test_declared_tool_is_first_class():
    mcp = _server().mcp
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert "search_reddit_test" in names

    tool = next(t for t in tools if t.name == "search_reddit_test")
    props = tool.inputSchema.get("properties", {})
    # The scraper method's signature drives the schema.
    assert set(props) == {"subreddit", "sort"}
    assert tool.inputSchema.get("required") == ["subreddit"]


@pytest.mark.anyio
async def test_declared_tool_runs():
    mcp = _server().mcp
    _content, structured = await mcp.call_tool(
        "search_reddit_test", {"subreddit": "python", "sort": "top"}
    )
    assert structured["data"] == [{"sub": "python", "sort": "top"}]


@pytest.mark.anyio
async def test_plugin_without_mcp_tools_has_no_dedicated_tool():
    mcp = _server().mcp
    names = {t.name for t in await mcp.list_tools()}
    assert "plain_test" not in names
    # ...but it is still reachable via the generic dispatcher.
    _content, structured = await mcp.call_tool(
        "scrape_with", {"name": "plain_test", "args": {"q": "x"}}
    )
    assert structured["scraper"] == "plain_test"
