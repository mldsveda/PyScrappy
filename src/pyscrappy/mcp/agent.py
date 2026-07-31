"""A minimal tool-calling agent that lets a local LLM use PyScrappy's scrapers.

Ollama (and other local runtimes) can't talk MCP directly, so this module is a
small bridge: it reads the same 22 tools the MCP server exposes, hands their
schemas to the model as tool definitions, and runs the tool-call loop itself.
No separate MCP host (Goose, Cline, …) required.

    pyscrappy chat --model qwen2.5 "get the current AAPL quote"

The only hard requirement is a model that supports tool calling (Llama 3.1,
Qwen 2.5, Mistral, …). Tool *selection* quality is up to the model.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

from pyscrappy.mcp.server import mcp

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5"
# A tool-calling model can loop (call, read result, call again). Bound it so a
# confused model can't spin forever.
MAX_STEPS = 8


async def _tool_specs() -> list[dict[str, Any]]:
    """Convert the MCP tool registry into Ollama's tool-definition format.

    Ollama uses the OpenAI function-calling shape, and a fastmcp tool's
    ``parameters`` is already JSON Schema, so this is a straight re-wrap — one
    source of truth.
    """
    # Ensure plugin-declared tools are registered before we read the tool list,
    # so the local-model agent sees them too (not just the MCP server).
    from pyscrappy.mcp.server import _register_plugin_tools

    _register_plugin_tools()
    tools = await mcp.list_tools()
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


async def _call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Run one scraper tool via the MCP registry, returning JSON for the model."""
    try:
        result = await mcp.call_tool(name, arguments)
    except Exception as exc:  # surface the failure to the model, don't crash the loop
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
    return json.dumps(result.structured_content, default=str)


async def run_agent(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    max_steps: int = MAX_STEPS,
    verbose: bool = False,
    ret_json: bool = False,
) -> str:
    """Answer ``prompt`` with a local model, letting it call PyScrappy scrapers."""
    tools = await _tool_specs()
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    async with httpx.AsyncClient(base_url=host, timeout=120.0) as client:
        for _ in range(max_steps):
            resp = await client.post(
                "/api/chat",
                json={"model": model, "messages": messages, "tools": tools, "stream": False},
            )
            resp.raise_for_status()
            message = resp.json()["message"]
            messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                content = message.get("content", "")
                if ret_json:
                    return json.dumps({"content": content})
                return content

            for call in tool_calls:
                fn = call["function"]
                name = fn["name"]
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    args = json.loads(args)
                if verbose and not ret_json:
                    print(f"  → {name}({json.dumps(args)})", file=sys.stderr)
                
                result = await _call_tool(name, args)

                # When --json is requested, return the raw tool JSON output immediately
                if ret_json:
                    return result

                messages.append({"role": "tool", "name": name, "content": result})

    error_msg = "Stopped: reached the maximum number of tool-calling steps."
    if ret_json:
        return json.dumps({"error": error_msg})
    return error_msg


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pyscrappy",
        description="Let a local LLM use PyScrappy's scrapers as tools (via Ollama).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Ask a local model a question it can answer with scrapers.")
    chat.add_argument("prompt", help="What to ask, in plain language.")
    chat.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})."
    )
    chat.add_argument(
        "--host", default=DEFAULT_HOST, help=f"Ollama host (default: {DEFAULT_HOST})."
    )
    chat.add_argument("--max-steps", type=int, default=MAX_STEPS, help="Max tool-calling rounds.")
    chat.add_argument("-v", "--verbose", action="store_true", help="Print each tool call.")
    chat.add_argument('--json', action="store_true", help="Prints output in JSON format only.")

    args = parser.parse_args()

    if args.command == "chat":
        import anyio

        answer = anyio.run(
            lambda: run_agent(
                args.prompt,
                model=args.model,
                host=args.host,
                max_steps=args.max_steps,
                verbose=args.verbose,
                ret_json=args.json
            )
        )
        print(answer)


if __name__ == "__main__":
    main()
