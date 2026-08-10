<p align="center">
  <img src="public/logo.png" alt="PyScrappy" width="480">
</p>

<h2 align="center">Adaptive Python web scraping toolkit (self-healing, stealth) + MCP server for AI agents</h2>

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Latest Release](https://img.shields.io/pypi/v/PyScrappy.svg)](https://pypi.org/project/PyScrappy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/mldsveda/PyScrappy/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/badge/pyscrappy)](https://pepy.tech/project/pyscrappy)
[![Glama quality](https://glama.ai/mcp/servers/mldsveda/PyScrappy/badges/score.svg)](https://glama.ai/mcp/servers/mldsveda/PyScrappy)
[![Documentation](https://img.shields.io/badge/docs-pyscrappy-117866.svg)](https://pyscrappy.vercel.app)
[![MCP Toplist](https://mcptoplist.com/badge/io.github.mldsveda%2Fpyscrappy.svg)](https://mcptoplist.com/server/io.github.mldsveda%2Fpyscrappy)

<!-- mcp-name: io.github.mldsveda/pyscrappy -->

PyScrappy is an AI-native web scraping toolkit that turns websites into structured, LLM-ready data. Use it as a Python library or expose it as an MCP server for AI agents.

📖 **Documentation:** [pyscrappy.vercel.app](https://pyscrappy.vercel.app)

## Key features

- **Generic scraper** — give it any URL, get back structured text, links, images, tables, and metadata
- **LLM-ready output** — `.to_markdown()` turns any result into clean Markdown; also `.to_json()` and `.to_dataframe()`
- **MCP server** — expose the scrapers as tools for AI agents (Claude, Cursor, local LLMs, …)
- **JS rendering** — optional Playwright backend for JavaScript-heavy sites
- **Custom selectors** — pass CSS selectors to extract exactly what you need
- **Chainable `Selector`** — navigate HTML directly with CSS/XPath, `find_all`, `find_by_text`, and `find_similar` (Scrapy/BeautifulSoup-style)
- **Adaptive (self-healing) selectors** — remember an element and relocate it by similarity when a site changes its markup, so scrapers don't silently break
- **Concurrent scraping** — `scrape_many` / `scrape_all` run scrapes in parallel
- **Proxy & scraping-API support** — route through a proxy or ScraperAPI/ScrapeOps for blocked sites
- **TLS-fingerprint impersonation** — `impersonate="chrome"` gets past anti-bot filters that block plain clients (optional `curl_cffi` backend)
- **Command-line extract** — `pyscrappy extract <url> out.md` scrapes a URL straight to a file, no code
- **Retry & rate-limiting** — built-in exponential backoff and per-domain rate limiting
- **Type-safe** — full type hints, `py.typed` marker
- **20+ built-in scrapers** — Wikipedia, IMDB, stocks, news, GitHub, Amazon/IKEA, YouTube, and [more](#built-in-scrapers)

## Installation

```sh
pip install pyscrappy
```

**Optional extras:**

```sh
# Browser support (for JS-rendered pages)
pip install 'pyscrappy[browser]'
playwright install chromium

# DataFrame support
pip install 'pyscrappy[dataframe]'

# MCP server (use PyScrappy's scrapers as AI-agent tools)
pip install 'pyscrappy[mcp]'

# Stealth (TLS-fingerprint impersonation to bypass anti-bot filters)
pip install 'pyscrappy[stealth]'

# Everything
pip install 'pyscrappy[all]'
```

## For AI agents

PyScrappy ships an [MCP server](#mcp-server-use-pyscrappy-from-an-ai-agent) that
exposes its scrapers as tools, so an agent (Claude, Cursor, an OpenAI agent, a
local LLM) can pull structured web data from any URL and hand it straight to the
model:

```text
AI agent  ──MCP tool call──▶  PyScrappy  ──fetch + extract──▶  Any website
   ▲                                                                │
   └──────────────  clean Markdown / JSON  ◀───────────────────────┘
```

```sh
pip install 'pyscrappy[mcp]'
claude mcp add pyscrappy pyscrappy-mcp
```

Then just ask: *"use pyscrappy to summarize the latest headlines from bbc.com."*
See [MCP server](#mcp-server-use-pyscrappy-from-an-ai-agent) for the full setup
and tool list.

### Local models (Ollama), no MCP host needed

Ollama can't talk MCP on its own, so normally you'd run a host (Goose, Cline, …)
in between. PyScrappy skips that with a built-in agent that talks to Ollama
directly and lets a local model call the scrapers as tools:

```sh
pip install 'pyscrappy[mcp]'                 # needs Python 3.10+
pyscrappy chat --model qwen2.5 "what's the current AAPL quote?"
```

It exposes the same 22 tools as the MCP server. The only requirement is a model
that supports **tool calling** (Llama 3.1, Qwen 2.5, Mistral, …); how well it
*picks* the right tool is up to the model. Point it at a remote Ollama with
`--host`, and pass `-v` to see each tool call.

## MCP server (use PyScrappy from an AI agent)

PyScrappy ships an optional [Model Context Protocol](https://modelcontextprotocol.io)
server, so an AI agent (e.g. Claude) can call PyScrappy's scrapers as tools and
get structured web data back.

<a href="https://glama.ai/mcp/servers/mldsveda/PyScrappy">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/mldsveda/PyScrappy/badges/card.svg" alt="PyScrappy MCP server" />
</a>

```sh
pip install 'pyscrappy[mcp]'
```

The MCP extra installs the standalone `fastmcp` package and requires Python 3.10
or newer. On Python 3.9 the core scraping library still works, but the MCP server
is unavailable.

This installs the `pyscrappy-mcp` command. It uses stdio by default for local MCP
clients; Streamable HTTP and legacy SSE are available for remote deployments:

```sh
pyscrappy-mcp          # stdio (default)
pyscrappy-mcp --http   # Streamable HTTP
pyscrappy-mcp --sse    # legacy SSE
```

You can also run the stdio server with `python -m pyscrappy.mcp`.

### Register with Claude Code

```sh
claude mcp add pyscrappy pyscrappy-mcp
```

### Register with Claude Desktop

Add to your `claude_desktop_config.json` and restart the app:

```json
{
  "mcpServers": {
    "pyscrappy": {
      "command": "pyscrappy-mcp"
    }
  }
}
```

> **Tip:** Claude Desktop does not inherit your shell `PATH`. If `pyscrappy-mcp`
> is not found, use the absolute path to the command (e.g. the one printed by
> `which pyscrappy-mcp`).

### Available tools

The server exposes **20+ tools**. The most common ones are **`scrape_url`** (any
URL → text, links, images, tables, metadata), **`scrape_wikipedia`**,
**`scrape_stock`**, **`scrape_news`**, and **`search_github`** — plus many more
covering image/YouTube/LinkedIn/Hacker News/book search, weather, crypto,
currency, dictionary, Amazon/Newegg/IKEA/SoundCloud, IMDB, and Zomato/Uber Eats.

To see the full, live list, ask the agent to call the **`list_available_scrapers`**
tool, or from a shell:

```sh
python -c "from pyscrappy import list_scrapers; print(', '.join(sorted(list_scrapers())))"
```

The `lookup_movie` tool needs a free [OMDb](https://www.omdbapi.com/apikey.aspx) API
key. Pass it to the server through your MCP client config, e.g. for Claude Desktop:

```json
{
  "mcpServers": {
    "pyscrappy": {
      "command": "pyscrappy-mcp",
      "env": { "OMDB_API_KEY": "your-key" }
    }
  }
}
```

Once registered, just ask the agent naturally, e.g. *"use pyscrappy to get the
latest headlines from bbc.co.uk and the AAPL stock quote."*

## Built-in scrapers

PyScrappy ships **24 built-in scrapers**, and every one that works without a
proxy is also exposed as an [MCP tool](#mcp-server-use-pyscrappy-from-an-ai-agent).

A few of them:

- **`GenericScraper`** — scrape any URL with auto-extraction (text, links, images, tables, metadata)
- **Data / research** — **`WikipediaScraper`**, **`StockScraper`** (Yahoo Finance), **`NewsScraper`** (RSS/Atom), **`GitHubScraper`**, **`HackerNewsScraper`**, plus weather, crypto, currency, dictionary, image, LinkedIn-jobs, and book search
- **E-commerce** — **`AmazonScraper`**, `NeweggScraper`, `IKEAScraper`
- **Social / media / food** — **`YouTubeScraper`**, SoundCloud, Zomato, Uber Eats (Instagram / Twitter / Spotify also ship, but are blocked and need a proxy)

…and many more. To see the full, live list:

```sh
python -c "from pyscrappy import list_scrapers; print(', '.join(sorted(list_scrapers())))"
```

**`IMDBScraper`** (`lookup_movie`) is the one exception that needs a key — a free
[OMDb](https://www.omdbapi.com/apikey.aspx) `OMDB_API_KEY` (see the
[MCP config](#available-tools) above for how to pass it).

## Plugins

PyScrappy is extensible: you can add your own scrapers, and third parties can
ship them as standalone `pyscrappy-<name>` packages. A registered scraper works
everywhere a built-in does, including the MCP server and the `pyscrappy chat`
agent, with no change to PyScrappy core.

**In your own code** — register with the decorator:

```python
from pyscrappy import BaseScraper, register_scraper, get_scraper
from pyscrappy.core.models import ScrapeResult, ScrapeMetadata

@register_scraper("reddit")
class RedditScraper(BaseScraper):
    def scrape(self, subreddit: str, **kwargs) -> ScrapeResult:
        data = self.fetch_and_parse(f"https://old.reddit.com/r/{subreddit}/.json")
        # ... build a list of dicts ...
        return ScrapeResult(data=[...], metadata=ScrapeMetadata(scraper="reddit"))

get_scraper("reddit")().scrape(subreddit="python")
```

**As a distributable package** — advertise an entry point in your
`pyproject.toml`, and PyScrappy discovers it once your package is installed:

```toml
[project.entry-points."pyscrappy.scrapers"]
reddit = "pyscrappy_reddit:RedditScraper"
```

After `pip install pyscrappy-reddit`, the scraper shows up in
`list_scrapers()`, and an AI agent can call it via the `scrape_with` MCP tool —
no core change required.

**First-class MCP tools (optional).** Add an `mcp_tools` mapping and your scraper
becomes a dedicated, typed MCP tool instead of only being reachable through the
generic `scrape_with` — its schema is derived from the method signature, so
agents get proper named arguments:

```python
@register_scraper("reddit")
class RedditScraper(BaseScraper):
    mcp_tools = {"search_reddit": "scrape"}   # tool name -> method

    def scrape(self, subreddit: str, sort: str = "hot") -> ScrapeResult:
        ...
```

See the [plugin template](plugin-template/) for a complete, copyable starting
point, and the [plugin guide](https://pyscrappy.vercel.app/docs/plugins/) for
the full walkthrough.

## Quick start

### Scrape any URL → clean, LLM-ready Markdown

```python
from pyscrappy import scrape

result = scrape("https://en.wikipedia.org/wiki/Web_scraping")

print(result.to_markdown())   # feed straight to an LLM
# ...or result.to_json() / result.to_dataframe()
```

Prefer raw fields? Every result is a `ScrapeResult` with `.data` (a list of
dicts):

```python
print(result.data[0]["metadata"]["title"])
print(result.data[0]["text"]["word_count"])
```

### Custom CSS selectors

```python
from pyscrappy import GenericScraper

with GenericScraper() as gs:
    result = gs.scrape(
        url="https://news.ycombinator.com",
        selectors={"title": ".titleline a", "score": ".score"},
    )
    for item in result.data:
        print(item["title"], item.get("score", ""))
```

### Navigate HTML with `Selector`

When you want to traverse markup directly (Scrapy/BeautifulSoup-style) rather than
get back structured dicts, use `Selector`:

```python
from pyscrappy import Selector

page = Selector(html)                             # or navigate any HTML string
page.css(".title::text").getall()                 # CSS with ::text / ::attr(name)
page.xpath("//a/@href").getall()                   # XPath (elements, text(), @attr)
page.find_all("h2", class_="title")                # BeautifulSoup-style search
page.find_by_text("Add to cart", tag="button")     # search by text content

first = page.css(".product")[0]
first.css(".price::text").get()                    # chainable
first.find_similar()                               # sibling elements shaped like this one
```

`css()` / `xpath()` return a `SelectorList` with `.get()` / `.getall()` / `.text()`.
`find_similar()` locates elements with the same tag and overlapping classes, handy
for pulling every card/row once you've found one.

### Adaptive (self-healing) selectors

A hard-coded CSS selector silently breaks the day a site changes its markup.
Adaptive selectors survive that: save a fingerprint of the element the first time,
and if the selector later matches nothing, relocate it by structural and textual
similarity instead of returning empty.

```python
from pyscrappy import Selector

# First run: match normally and remember this element under an id.
page = Selector(html_v1, url="https://shop.example.com")
price = page.css(".price", auto_save=True, adaptive_id="price").get()

# Later, after a redesign renamed ".price" — heal instead of breaking:
page = Selector(html_v2, url="https://shop.example.com")
result = page.css(".price", adaptive=True, adaptive_id="price")
print(result.get(), "→ confidence:", result.adaptive_confidence)
```

How the relocation decides — and where it's stronger than a naive similarity match:

- **Weighted signals, not a flat average.** A stable `id` / `data-*` hook counts
  far more than a sibling-tag list, so weak signals can't outvote strong ones.
- **Anchor-relative.** It remembers the nearest stable ancestor (an id'd / `data-*`
  container) and depth, so it survives layout reshuffles that move absolute positions.
- **Volatility-aware text.** Prices, dates, and counts are down-weighted, so
  healing stays reliable on exactly the fields that change most between scrapes.
- **Confidence-scored.** `SelectorList.adaptive_confidence` (0-100) tells you how
  sure the relocation was; `threshold=` sets the minimum to accept.

Fingerprints persist in a small JSON store (`~/.pyscrappy/adaptive.json` by
default, or `$PYSCRAPPY_HOME`), namespaced by site so the same `adaptive_id` on
two sites never collides. Adaptive is entirely opt-in: without `adaptive=True`, a
broken selector still just returns empty, exactly as before.

### Site-specific scrapers

Every built-in scraper follows the same pattern — instantiate, `scrape(...)`,
read `result.data` (or `.to_dataframe()` / `.to_markdown()`):

```python
from pyscrappy import WikipediaScraper

with WikipediaScraper() as ws:
    result = ws.scrape(query="Python (programming language)", mode="summary")
    print(result.data[0]["text"])
```

Each scraper has its own arguments (Wikipedia, stocks, IMDB, news, YouTube,
Amazon/Newegg/IKEA, Uber Eats, and more — see the [full list](#built-in-scrapers)).
For per-scraper arguments and examples, see the
[documentation](https://pyscrappy.vercel.app/docs/scrapers/).

### From the command line

Scrape a URL straight to a file without writing any code — the output format is
inferred from the file extension:

```sh
pyscrappy extract https://example.com out.md      # clean Markdown
pyscrappy extract https://example.com out.json    # structured JSON
pyscrappy extract https://example.com out.txt     # extracted page text
pyscrappy extract https://example.com out.html    # raw fetched HTML

# Narrow to elements matching a CSS selector, or render JS first:
pyscrappy extract https://example.com items.txt --css-selector ".product"
pyscrappy extract https://example.com page.md --render-js
```

## Configuration

```python
from pyscrappy import ScraperConfig, GenericScraper

config = ScraperConfig(
    timeout=20.0,            # request timeout in seconds
    max_retries=3,           # retry failed requests
    rate_limit=2.0,          # seconds between requests per domain
    proxy="http://...",      # proxy URL, or a list to rotate through
    scraper_api=None,        # route via a scraping-API service (see below)
    headless=True,           # browser runs headless
    render_js="auto",        # auto-detect if JS rendering is needed
    cache_ttl=0,             # response cache TTL in seconds (0 = disabled)
    impersonate=None,        # e.g. "chrome" to spoof a browser's TLS fingerprint (see below)
)

with GenericScraper(config) as gs:
    result = gs.scrape(url="https://example.com")
```

### Proxies and blocked sites

Some sites (e.g. eBay, Instagram, Twitter/X, Spotify) block direct automated
requests. PyScrappy supports two ways to get through them.

**A proxy** (or a rotating list) — applies to both the HTTP and browser backends:

```python
from pyscrappy import ScraperConfig, AmazonScraper

# Single proxy
config = ScraperConfig(proxy="http://user:pass@host:port")

# Rotating list (one picked per request)
config = ScraperConfig(proxy=["http://p1:8080", "http://p2:8080"])
```

**A scraping-API service** (ScraperAPI, ScrapeOps, ScrapingBee) — routes requests
through the service, which handles proxies and anti-bot challenges for you:

```python
config = ScraperConfig(scraper_api={
    "provider": "scraperapi",   # or "scrapeops", "scrapingbee"
    "api_key": "YOUR_KEY",
    "render_js": True,           # optional
})

# Now any scraper works through the service, unchanged:
with AmazonScraper(config) as scraper:
    result = scraper.scrape(query="laptop")
```

This is the reliable way to use the scrapers marked "needs proxy" above.

**TLS-fingerprint impersonation** — many anti-bot systems block a plain HTTP
client by its TLS/JA3 fingerprint before serving any content. Set `impersonate`
to mimic a real browser's fingerprint and get past that class of block without a
headless browser:

```python
from pyscrappy import ScraperConfig, GenericScraper

# needs the optional extra:  pip install 'pyscrappy[stealth]'
config = ScraperConfig(impersonate="chrome")   # or "chrome124", "safari", "firefox"

with GenericScraper(config) as gs:
    result = gs.scrape("https://example.com")
```

Impersonation currently applies to the **synchronous** path only; setting it on
an async client raises a clear error. All the usual retry, rate-limiting,
caching, and robots handling still apply.

### Concurrent scraping

Scraping is I/O-bound, so running several scrapes at once parallelizes the
network waits. `scrape_many` runs one scraper over many inputs; `scrape_all`
runs a mix of scrapers together. Both preserve input order.

```python
from pyscrappy import scrape_many, scrape_all, AmazonScraper, WikipediaScraper, NewsScraper

# One scraper, many queries, concurrently:
results = scrape_many(AmazonScraper, [{"query": "laptop"}, {"query": "phone"}])

# Different scrapers at once:
results = scrape_all([
    lambda: WikipediaScraper().scrape(query="Python"),
    lambda: NewsScraper().scrape(feed_url="https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
])
```

### Response caching

Set `cache_ttl` to a positive number of seconds to cache successful GET
responses. Repeated requests for the same URL (and query params) within the TTL
are served from cache, skipping both the network and the rate limiter. Caching
is **disabled by default** (`cache_ttl=0`).

```python
from pyscrappy import WikipediaScraper
from pyscrappy import ScraperConfig

config = ScraperConfig(cache_ttl=300)   # cache for 5 minutes

with WikipediaScraper(config) as ws:
    ws.scrape(query="Python")   # fetched over the network
    ws.scrape(query="Python")   # served from cache
```

The cache is in memory and shared across scraper instances in the same process
(so it also speeds up repeated calls through the MCP server), and is cleared
when the process exits. Call `HttpClient.clear_cache()` to empty it manually.

## Dependencies

**Required:** `httpx`, `beautifulsoup4`, `lxml`

**Optional:** `playwright` (JS rendering), `pandas` (DataFrames), `fastmcp`
(MCP server, Python 3.10+)

## License

[MIT](https://github.com/mldsveda/PyScrappy/blob/main/LICENSE)

## Contributing

All contributions welcome. See [Issues](https://github.com/mldsveda/PyScrappy/issues).

**This package is for educational and research purposes.**
