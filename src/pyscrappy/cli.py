"""The ``pyscrappy`` command-line interface.

Kept free of any MCP imports so the plain scraping commands (``extract``) work on
every supported Python version. The ``chat`` command needs the MCP/agent stack
(Python >=3.10), so it's imported lazily only when that command is invoked.
"""

from __future__ import annotations

import argparse


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
        description="PyScrappy CLI: extract a URL to a file, or chat with a local LLM.",
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

    chat = sub.add_parser(
        "chat",
        help="Ask a local model a question it can answer with scrapers (needs pyscrappy[mcp]).",
    )
    chat.add_argument("prompt", help="What to ask, in plain language.")
    chat.add_argument("--model", default=None, help="Ollama model (default: qwen2.5).")
    chat.add_argument("--host", default=None, help="Ollama host (default: http://localhost:11434).")
    chat.add_argument("--max-steps", type=int, default=None, help="Max tool-calling rounds.")
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
        # The agent/MCP stack requires Python >=3.10 and the [mcp] extra; import it
        # only now so `pyscrappy extract` stays usable without either.
        try:
            import anyio

            from pyscrappy.mcp.agent import DEFAULT_HOST, DEFAULT_MODEL, MAX_STEPS, run_agent
        except ImportError as exc:
            raise SystemExit(
                "The 'chat' command needs the MCP/agent extra (Python >=3.10): "
                "pip install 'pyscrappy[mcp]'"
            ) from exc

        answer = anyio.run(
            lambda: run_agent(
                args.prompt,
                model=args.model or DEFAULT_MODEL,
                host=args.host or DEFAULT_HOST,
                max_steps=args.max_steps or MAX_STEPS,
                verbose=args.verbose,
                json_output=args.json,
            )
        )
        print(answer)


if __name__ == "__main__":
    main()
