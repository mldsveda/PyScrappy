<div align="center">
  <img src="https://raw.githubusercontent.com/mldsveda/PyScrappy/main/PyScrappy.png">
  <hr>
</div>

## PyScrappy: robust, all-in-one Python web scraping toolkit

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI Latest Release](https://img.shields.io/pypi/v/PyScrappy.svg)](https://pypi.org/project/PyScrappy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/mldsveda/PyScrappy/blob/main/LICENSE)
[![Downloads](https://static.pepy.tech/badge/pyscrappy)](https://pepy.tech/project/pyscrappy)

PyScrappy is a Python toolkit for web scraping that works out of the box. Point it at any URL and get structured data back — or use built-in scrapers for Wikipedia, IMDB, Yahoo Finance, news feeds, and more.

### Key features

- **Generic scraper** — give it any URL, get back structured text, links, images, tables, and metadata
- **Auto-pagination** — automatically follows "next page" links
- **JS rendering** — optional Playwright backend for JavaScript-heavy sites
- **Custom selectors** — pass CSS selectors to extract exactly what you need
- **Built-in scrapers** — Wikipedia, IMDB, Yahoo Finance, news (RSS), image search, Amazon, LinkedIn
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

### IMDB

```python
from pyscrappy import IMDBScraper

with IMDBScraper() as scraper:
    result = scraper.scrape(genre="sci-fi", max_pages=2)
    df = result.to_dataframe()
    print(df[["title", "year", "rating"]])
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
    proxy="http://...",      # HTTP/SOCKS proxy
    headless=True,           # browser runs headless
    render_js="auto",        # auto-detect if JS rendering is needed
)

with GenericScraper(config) as gs:
    result = gs.scrape(url="https://example.com")
```

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

### E-Commerce (Alibaba, Flipkart, Snapdeal)

```python
from pyscrappy import AlibabaScraper, FlipkartScraper, SnapdealScraper

with FlipkartScraper() as scraper:
    result = scraper.scrape(query="laptop", max_pages=2)
    df = result.to_dataframe()
```

### Food Delivery (Swiggy, Zomato)

```python
from pyscrappy import SwiggyScraper, ZomatoScraper

# These are JS-heavy — use render_js=True for best results
with SwiggyScraper() as scraper:
    result = scraper.scrape(city="bangalore", render_js=True)
```

## Built-in scrapers

| Scraper | What it does | Needs browser? |
|---------|-------------|----------------|
| `GenericScraper` | Scrape any URL with auto-extraction | Optional |
| **Data / Research** | | |
| `WikipediaScraper` | Articles, sections, infoboxes | No |
| `IMDBScraper` | Movies by genre, search, charts | No |
| `StockScraper` | Quotes, history, profiles (Yahoo Finance) | No |
| `NewsScraper` | RSS/Atom feeds, article extraction | No |
| `ImageSearchScraper` | Image search + download | No |
| `LinkedInJobsScraper` | Public job listings | No |
| **E-Commerce** | | |
| `AmazonScraper` | Product search | No |
| `AlibabaScraper` | Product search | No |
| `FlipkartScraper` | Product search | No |
| `SnapdealScraper` | Product search | No |
| **Social Media** | | |
| `YouTubeScraper` | Video search, channel scraping | Optional |
| `InstagramScraper` | Profiles, hashtag posts | Recommended |
| `TwitterScraper` | Tweet search | Recommended |
| **Music** | | |
| `SpotifyScraper` | Track/playlist search | Recommended |
| `SoundCloudScraper` | Track search | Optional |
| **Food Delivery** | | |
| `SwiggyScraper` | Restaurant listings | Recommended |
| `ZomatoScraper` | Restaurant listings | Recommended |

## MCP server (use PyScrappy from an AI agent)

PyScrappy ships an optional [Model Context Protocol](https://modelcontextprotocol.io)
server, so an AI agent (e.g. Claude) can call PyScrappy's scrapers as tools and
get structured web data back.

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
| `search_soundcloud` | SoundCloud track search (uses the browser backend) |
| `scrape_zomato` | Restaurant listings by city |

Once registered, just ask the agent naturally — e.g. *"use pyscrappy to get the
latest headlines from bbc.co.uk and the AAPL stock quote."*

## Dependencies

**Required:** `httpx`, `beautifulsoup4`, `lxml`

**Optional:** `playwright` (JS rendering), `pandas` (DataFrames), `mcp` (MCP server)

## License

[MIT](https://github.com/mldsveda/PyScrappy/blob/main/LICENSE)

## Contributing

All contributions welcome. See [Issues](https://github.com/mldsveda/PyScrappy/issues).

**This package is for educational and research purposes.**
