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
    json_output: bool = False,
) -> str:
    """Answer ``prompt`` with a local model, letting it call PyScrappy scrapers.

    Talks to an Ollama-compatible ``/api/chat`` endpoint. Returns the model's final text
    answer by default, or the latest raw tool result when ``json_output`` is enabled.
    """
    tools = await _tool_specs()
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    last_result: str | None = None

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
                answer = message.get("content", "")
                if json_output:
                    return (
                        last_result if last_result is not None else json.dumps({"answer": answer})
                    )
                return answer

            for call in tool_calls:
                fn = call["function"]
                name = fn["name"]
                args = fn.get("arguments") or {}
                if isinstance(args, str):  # some models return arguments as a JSON string
                    args = json.loads(args)
                if verbose:
                    print(f"  → {name}({json.dumps(args)})", file=sys.stderr)
                last_result = await _call_tool(name, args)
                messages.append({"role": "tool", "name": name, "content": last_result})

    stopped = "Stopped: reached the maximum number of tool-calling steps."
    if json_output:
        return last_result if last_result is not None else json.dumps({"error": stopped})
    return stopped


def run_extract(
    url: str,
    out_path: str,
    css_selector: str | None = None,
    render_js: bool = False,
) -> str:
    """Scrape ``url`` and write the result to ``out_path``. The output format is
    chosen from the file extension:

    - ``.md``   -> Markdown (``ScrapeResult.to_markdown``)
    - ``.json`` -> JSON (``ScrapeResult.to_json``)
    - ``.txt``  -> extracted page text
    - ``.html`` -> raw page HTML

    With ``--css-selector`` the matched elements' text is extracted instead of the
    whole page. Returns a short status line for the CLI to print.
    """
    from pyscrappy import GenericScraper, scrape

    ext = out_path.rsplit(".", 1)[-1].lower() if "." in out_path else ""
    if ext not in {"json", "md", "txt", "html"}:
        raise ValueError(f"unsupported output extension {ext!r}; use .md, .json, .txt, or .html")

    if ext == "html":
        # Raw HTML: the structured scrape result doesn't retain the source markup,
        # so fetch the page's HTML directly.
        with GenericScraper() as gs:
            content = gs.http.get_html(url)
    else:
        selectors = {"match": css_selector} if css_selector else None
        result = scrape(url, selectors=selectors, render_js=render_js)
        if ext == "json":
            content = result.to_json()
        elif ext == "md":
            content = result.to_markdown()
        else:  # txt
            if css_selector:
                content = "\n".join(row.get("match", "") for row in result.data)
            else:
                content = "\n\n".join(item.get("text", {}).get("text", "") for item in result.data)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"wrote {len(content)} chars to {out_path}"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pyscrappy",
        description="Let a local LLM use PyScrappy's scrapers as tools (via Ollama).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser(
        "extract", help="Scrape a URL straight to a file (.md/.json/.txt/.html)."
    )
    extract.add_argument("url", help="The URL to scrape.")
    extract.add_argument("output", help="Output file; format inferred from its extension.")
    extract.add_argument(
        "--css-selector", default=None, help="Extract only elements matching this CSS selector."
    )
    extract.add_argument(
        "--render-js", action="store_true", help="Render JavaScript with a browser first."
    )

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
    chat.add_argument("--json", action="store_true", help="Print the raw scraper result as JSON.")

    args = parser.parse_args()

    if args.command == "extract":
        status = run_extract(
            args.url,
            args.output,
            css_selector=args.css_selector,
            render_js=args.render_js,
        )
        print(status)
        return

    if args.command == "chat":
        import anyio

        answer = anyio.run(
            lambda: run_agent(
                args.prompt,
                model=args.model,
                host=args.host,
                max_steps=args.max_steps,
                verbose=args.verbose,
                json_output=args.json,
            )
        )
        print(answer)


if __name__ == "__main__":
    main()
