"""Tests for the Ollama tool-calling agent (pyscrappy.mcp.agent).

The Ollama HTTP endpoint and the scrapers are both mocked, so these run with no
network, no Ollama install, and no live sites.
"""

import json

import httpx
import pytest

# The agent module imports the MCP SDK (mcp.server.fastmcp). It's an optional
# dependency (pyscrappy[mcp]); if it isn't installed, skip these tests cleanly
# instead of erroring the whole collection.
pytest.importorskip("mcp.server.fastmcp")

from pyscrappy.mcp import agent  # noqa: E402  (import after the skip guard)


@pytest.mark.anyio
async def test_tool_specs_wrap_mcp_tools():
    specs = await agent._tool_specs()
    # At least the core scraper tools plus the generic plugin dispatch tools.
    assert len(specs) >= 22
    spec = specs[0]
    assert spec["type"] == "function"
    fn = spec["function"]
    # Name, description and a JSON-Schema parameters block come straight from MCP.
    assert isinstance(fn["name"], str) and fn["name"]
    assert "parameters" in fn and fn["parameters"]["type"] == "object"
    names = {s["function"]["name"] for s in specs}
    assert {"scrape_url", "scrape_stock", "define_word"} <= names
    # Plugin-aware dispatch tools are exposed to the agent too.
    assert {"scrape_with", "list_available_scrapers"} <= names


def _mock_ollama(monkeypatch, responses):
    """Patch httpx.AsyncClient to replay a scripted list of /api/chat messages."""
    replies = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": next(replies)})

    transport = httpx.MockTransport(handler)
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


@pytest.mark.anyio
async def test_direct_answer_no_tools(monkeypatch):
    _mock_ollama(monkeypatch, [{"role": "assistant", "content": "Hello!"}])
    answer = await agent.run_agent("hi", model="test")
    assert answer == "Hello!"


@pytest.mark.anyio
async def test_tool_call_round_trip(monkeypatch):
    # Turn 1: model asks for a tool. Turn 2: model answers using the result.
    _mock_ollama(
        monkeypatch,
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"function": {"name": "define_word", "arguments": {"word": "python"}}}
                ],
            },
            {"role": "assistant", "content": "A python is a snake."},
        ],
    )

    called = {}

    async def fake_call_tool(name, arguments):
        called["name"] = name
        called["args"] = arguments
        return json.dumps({"data": [{"definition": "a snake"}]})

    monkeypatch.setattr(agent, "_call_tool", fake_call_tool)

    answer = await agent.run_agent("define python", model="test")
    assert answer == "A python is a snake."
    assert called == {"name": "define_word", "args": {"word": "python"}}


@pytest.mark.anyio
async def test_string_arguments_are_parsed(monkeypatch):
    # Some models return `arguments` as a JSON string rather than an object.
    _mock_ollama(
        monkeypatch,
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "define_word", "arguments": '{"word": "x"}'}}],
            },
            {"role": "assistant", "content": "done"},
        ],
    )
    seen = {}

    async def fake_call_tool(name, arguments):
        seen["args"] = arguments
        return "{}"

    monkeypatch.setattr(agent, "_call_tool", fake_call_tool)
    await agent.run_agent("x", model="test")
    assert seen["args"] == {"word": "x"}


@pytest.mark.anyio
async def test_max_steps_guard(monkeypatch):
    # A model that always calls a tool must not loop forever.
    loop_reply = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "define_word", "arguments": {"word": "x"}}}],
    }
    _mock_ollama(monkeypatch, [loop_reply] * 10)

    async def fake_call_tool(name, arguments):
        return "{}"

    monkeypatch.setattr(agent, "_call_tool", fake_call_tool)
    answer = await agent.run_agent("x", model="test", max_steps=3)
    assert "maximum number of tool-calling steps" in answer


@pytest.mark.anyio
async def test_tool_error_is_reported_to_model(monkeypatch):
    # A scraper that raises should return an error payload, not crash the loop.
    async def boom(name, arguments):
        raise RuntimeError("network down")

    # Exercise the real _call_tool error handling via a failing mcp.call_tool.
    async def failing_call_tool(name, args):
        raise RuntimeError("network down")

    monkeypatch.setattr(agent.mcp, "call_tool", failing_call_tool)
    result = await agent._call_tool("define_word", {"word": "x"})
    payload = json.loads(result)
    assert "error" in payload and "network down" in payload["error"]
