## PyScrappy: robust, all-in-one Python web scraping toolkit

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Latest Release](https://img.shields.io/pypi/v/PyScrappy.svg)](https://pypi.org/project/PyScrappy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/mldsveda/PyScrappy/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/badge/pyscrappy)](https://pepy.tech/project/pyscrappy)
[![Glama quality](https://glama.ai/mcp/servers/mldsveda/PyScrappy/badges/score.svg)](https://glama.ai/mcp/servers/mldsveda/PyScrappy)
[![Documentation](https://img.shields.io/badge/docs-pyscrappy-117866.svg)](https://pyscrappy.vercel.app)

<!-- mcp-name: io.github.mldsveda/pyscrappy -->

PyScrappy is a Python toolkit for web scraping that works out of the box. Point it at any URL and get structured data back — or use built-in scrapers for Wikipedia, IMDB, Yahoo Finance, news feeds, and more.

📖 **Documentation:** [pyscrappy.vercel.app](https://pyscrappy.vercel.app)

### Key features

- **Generic scraper** — give it any URL, get back structured text, links, images, tables, and metadata
- **Auto-pagination** — automatically follows "next page" links
- **JS rendering** — optional Playwright backend for JavaScript-heavy sites
- **Custom selectors** — pass CSS selectors to extract exactly what you need
- **20+ built-in scrapers** — Wikipedia, IMDB, stocks, news, GitHub, Hacker News, books, weather, Amazon/Newegg/IKEA, LinkedIn, YouTube, Uber Eats, and more
- **MCP server** — expose the scrapers as tools for AI agents (Claude, Cursor, local LLMs, …)
- **Concurrent scraping** — `scrape_many` / `scrape_all` run scrapes in parallel
- **Proxy & scraping-API support** — route through a proxy or ScraperAPI/ScrapeOps for blocked sites
- **Clean API** — every scraper returns a `ScrapeResult` with `.to_dataframe()` and `.to_json()`
- **Retry & rate-limiting** — built-in exponential backoff and per-domain rate limiting
- **Type-safe** — full type hints, `py.typed` marker

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

# Everything
pip install 'pyscrappy[all]'
```

## Quick start

### Scrape any URL (one-liner)

```python
from pyscrappy import scrape

result = scrape("https://en.wikipedia.org/wiki/Web_scraping")
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

### Wikipedia

```python
from pyscrappy import WikipediaScraper

with WikipediaScraper() as ws:
    result = ws.scrape(query="Python (programming language)", mode="summary")
    print(result.data[0]["text"])
```

### Stock data

```python
from pyscrappy import StockScraper

with StockScraper() as ss:
    result = ss.scrape(symbol="AAPL", mode="history", period="1mo")
    df = result.to_dataframe()
    print(df.head())
```

### IMDB (via OMDb API)

IMDB's own pages are protected by an anti-bot challenge, so PyScrappy fetches IMDB
data through the free [OMDb API](https://www.omdbapi.com/). Set an OMDb API key in
the `OMDB_API_KEY` environment variable (or pass `api_key=...`).

```python
from pyscrappy import IMDBScraper

with IMDBScraper() as scraper:      # reads OMDB_API_KEY from the environment
    # Search by title
    result = scraper.scrape(query="inception")
    # ...or look up a specific IMDB id
    result = scraper.scrape(query="tt1375666")
    df = result.to_dataframe()
    print(df[["title", "year", "rating", "genre"]])
```

### News (RSS feeds)

```python
from pyscrappy import NewsScraper

with NewsScraper() as ns:
    result = ns.scrape(feed_url="https://rss.nytimes.com/services/xml/rss/nyt/World.xml")
    for article in result.data[:5]:
        print(article["title"])
```

### Image search

```python
from pyscrappy import ImageSearchScraper

with ImageSearchScraper() as iss:
    result = iss.scrape(query="golden retriever", max_images=10, download_to="./dogs")
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

This is the reliable way to use the scrapers marked "needs proxy" below.

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

### YouTube

```python
from pyscrappy import YouTubeScraper

with YouTubeScraper() as scraper:
    result = scraper.scrape(query="python tutorial", max_results=10)
    for video in result.data:
        print(video["title"], video.get("views", ""))
```

### SoundCloud

```python
from pyscrappy import SoundCloudScraper

with SoundCloudScraper() as scraper:
    result = scraper.scrape(query="lo-fi beats", max_results=10)
```

### E-Commerce (Amazon, Newegg, IKEA)

```python
from pyscrappy import AmazonScraper, NeweggScraper, IKEAScraper

# Amazon — general marketplace
with AmazonScraper() as scraper:
    result = scraper.scrape(query="laptop", max_pages=2)

# Newegg — electronics / computer hardware
with NeweggScraper() as scraper:
    result = scraper.scrape(query="graphics card", max_pages=2)

# IKEA — furniture / home (uses IKEA's JSON search API).
# Prices and products are per-country: pass the store's country/lang.
with IKEAScraper(country="gb", lang="en") as scraper:   # or "us"/"en", "de"/"de", …
    result = scraper.scrape(query="desk", max_results=24)
    df = result.to_dataframe()
```

### Food Delivery (Zomato, Uber Eats)

```python
from pyscrappy import ZomatoScraper, UberEatsScraper

with ZomatoScraper() as scraper:
    result = scraper.scrape(city="bangalore", max_results=20)

# Uber Eats: restaurants by city (any country Uber Eats operates in),
# then the full menu of any restaurant. Pass the country's locale.
with UberEatsScraper(locale="gb") as scraper:
    result = scraper.scrape(city="London", max_results=30)
    store = result.data[0]
    menu = scraper.get_menu(store["url"])   # items with prices
```

## Built-in scrapers

Every scraper that works without a proxy is also exposed as an [MCP tool](#mcp-server-use-pyscrappy-from-an-ai-agent) (last column).

| Scraper | What it does | Browser? | MCP tool |
|---------|-------------|----------|----------|
| `GenericScraper` | Scrape any URL with auto-extraction | Optional | `scrape_url` |
| **Data / Research** | | | |
| `WikipediaScraper` | Articles, sections, infoboxes | No | `scrape_wikipedia` |
| `IMDBScraper` | Movie/TV info by title or id (via OMDb API; needs `OMDB_API_KEY`) | No | `lookup_movie` |
| `StockScraper` | Quotes, history, profiles (Yahoo Finance) | No | `scrape_stock` |
| `NewsScraper` | RSS/Atom feeds, article extraction | No | `scrape_news` |
| `ImageSearchScraper` | Image search + download | No | `search_images` |
| `LinkedInJobsScraper` | Public job listings | No | `search_linkedin_jobs` |
| `GitHubScraper` | Repository search (stars, language, …) via GitHub API | No | `search_github` |
| `HackerNewsScraper` | Story search (points, comments) via HN API | No | `search_hackernews` |
| `OpenLibraryScraper` | Book search (title, author, year) via Open Library | No | `search_books` |
| `WeatherScraper` | Current weather by place, via Open-Meteo (no key) | No | `get_weather` |
| `CryptoScraper` | Crypto prices / market cap via CoinGecko (no key) | No | `get_crypto` |
| `CurrencyScraper` | Currency exchange rates + conversion (no key) | No | `convert_currency` |
| `DictionaryScraper` | Word definitions, examples (Free Dictionary API) | No | `define_word` |
| **E-Commerce** | | | |
| `AmazonScraper` | Product search | No | `search_amazon` |
| `NeweggScraper` | Electronics / computer hardware search | No | `search_newegg` |
| `IKEAScraper` | Furniture / home search, per-country prices (JSON API) | No | `search_ikea` |
| **Social Media** | | | |
| `YouTubeScraper` | Video search, channel scraping | Optional | `search_youtube` |
| `InstagramScraper` | Profiles, hashtag posts (blocked; needs proxy) | Recommended | — |
| `TwitterScraper` | Tweet search (blocked; needs proxy) | Recommended | — |
| **Music** | | | |
| `SpotifyScraper` | Track/playlist search (blocked; needs proxy) | Recommended | — |
| `SoundCloudScraper` | Track search | Optional | `search_soundcloud` |
| **Food Delivery** | | | |
| `ZomatoScraper` | Restaurant listings by city | Recommended | `scrape_zomato` |
| `UberEatsScraper` | Restaurants by city + full menus (any Uber Eats country) | No | `search_ubereats`, `get_ubereats_menu` |

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

This installs a `pyscrappy-mcp` command (a stdio MCP server). You can also run it
with `python -m pyscrappy.mcp`.

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

| Tool | Description |
|------|-------------|
| `scrape_url` | Scrape any URL — text, links, images, tables, metadata |
| `scrape_wikipedia` | Fetch a Wikipedia article (`full` / `paragraphs` / `headers`) |
| `scrape_stock` | Yahoo Finance quotes, history, and profiles |
| `scrape_news` | RSS/Atom feeds, auto-discovered site feeds, or a single article |
| `search_images` | Image search (returns URLs + metadata) |
| `search_youtube` | YouTube video search |
| `search_linkedin_jobs` | Public LinkedIn job listings |
| `search_github` | GitHub repository search (stars, language, …) |
| `search_hackernews` | Hacker News story search (points, comments) |
| `search_books` | Book search via Open Library (title, author, year) |
| `get_weather` | Current weather for a place (no key) |
| `get_crypto` | Cryptocurrency prices and market data (CoinGecko) |
| `convert_currency` | Exchange rates and currency conversion |
| `define_word` | Word definitions and examples |
| `search_amazon` | Amazon product search |
| `search_newegg` | Newegg electronics / computer hardware search |
| `search_ikea` | IKEA furniture / home search |
| `search_soundcloud` | SoundCloud track search (uses the browser backend) |
| `lookup_movie` | Movie/TV info from IMDB by title or id (via OMDb; needs `OMDB_API_KEY`) |
| `scrape_zomato` | Restaurant listings by city |
| `search_ubereats` | Uber Eats restaurants by city |
| `get_ubereats_menu` | An Uber Eats restaurant's full menu (from its store URL) |

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

## Dependencies

**Required:** `httpx`, `beautifulsoup4`, `lxml`

**Optional:** `playwright` (JS rendering), `pandas` (DataFrames), `mcp` (MCP server)

## License

[MIT](https://github.com/mldsveda/PyScrappy/blob/main/LICENSE)

## Contributing

All contributions welcome. See [Issues](https://github.com/mldsveda/PyScrappy/issues).

**This package is for educational and research purposes.**
