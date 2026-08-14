# Changelog

All notable changes to PyScrappy are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [1.5.4] - 2026-08-14

### Added
- **`ScrapeResult.to_ndjson()` and `.to_yaml()` exporters**, and `save()` now infers `.ndjson`/`.jsonl` and `.yaml`/`.yml` from the file extension. YAML uses the optional `pyscrappy[yaml]` extra and is `safe_load`-round-trippable (#145).

### Fixed
- `Retry-After` is parsed for both the delay-seconds and HTTP-date forms (a date value no longer crashes the request), and it is now honored on `503` responses as well as `429`, across the sync and async clients (#143).
- Derived/chained selectors (`page.css(...)[0]`, `find_all`, `find_similar`, `parent`, etc.) now preserve the parent's `url` and adaptive store, so per-site adaptive namespacing and healing work through a selector chain (#144).

## [1.5.3] - 2026-08-12

### Fixed
- `Selector.xpath()` no longer crashes on a scalar XPath like `count(...)` or `boolean(...)`; the value is returned as a single-item string result (#136).
- `MetadataExtractor` drops empty `keywords` entries produced by trailing or repeated commas, e.g. `"a, , b,"` -> `["a", "b"]` (#137).

### Changed
- `AdaptiveStore.save()` writes the fingerprint store atomically (temp file + `os.replace`), so a crash mid-write or a concurrent write can no longer corrupt `adaptive.json` (#138).

## [1.5.2] - 2026-08-10

### Fixed
- README logo uses an absolute raw-GitHub URL so it renders on the PyPI project page (a repo-relative path only resolves on GitHub).

## [1.5.1] - 2026-08-10

### Added
- **Adaptive (self-healing) selectors.** `Selector.css` gains `auto_save=True` to fingerprint the matched element and `adaptive=True` to relocate it by similarity when the selector later matches nothing, so scrapers survive site redesigns. Relocation uses weighted signals (a stable `id`/`data-*` hook outweighs weaker ones), anchor-relative fingerprints (nearest stable ancestor + depth), volatility-aware text scoring (prices/dates/counts down-weighted), and tag-pruning before scoring. Returns a confidence score and runner-up gap (`SelectorList.adaptive_confidence`); fingerprints persist in a JSON store namespaced by site.
- README logo header and an updated title/tagline.

## [1.5.0] - 2026-08-10

### Added
- **Chainable `Selector` parser.** Navigate HTML directly (Scrapy/BeautifulSoup-style): `css()`/`xpath()` with `::text` / `::attr(name)` pseudo-elements, `find_all()`, `find_by_text()`, and `find_similar()`. Returns a `SelectorList` with `.get()`/`.getall()`/`.text()`. Usable standalone on an HTML string.
- **`pyscrappy extract` CLI.** Scrape a URL straight to a file with the format inferred from the extension (`.md`/`.json`/`.txt`/`.html`), plus `--css-selector` and `--render-js`.
- **TLS-fingerprint impersonation.** `ScraperConfig(impersonate="chrome")` routes the sync HTTP client through a `curl_cffi` session that mimics a real browser's fingerprint, getting past anti-bot filters that block plain clients. Optional `pyscrappy[stealth]` extra; the async path raises a clear error when set.

### Fixed
- `extract` moved to an MCP-free `pyscrappy.cli` module so the CLI works on Python 3.9 (the MCP stack requires 3.10+).

### CI
- The weekly live-scraper integration job is now non-blocking and writes a per-scraper pass/fail summary, so a site blocking a CI IP no longer shows as a red failure.

## [1.4.7] - 2026-08-09

### Fixed
- `to_markdown()` escapes pipes and newlines in table cells, so a cell containing `|` or a line break no longer corrupts the rendered table.
- Cache key no longer produces a double `?` when the URL already has a query string, closing a second collision case.

## [1.4.6] - 2026-08-07

### Fixed
- `TableExtractor` keeps ragged rows (aligning cells by position, padding short rows and preserving extra cells) instead of silently dropping any row whose cell count differs from the header.
- Hacker News docstrings now say `num_comments`, matching the key the scraper actually emits.

## [1.4.5] - 2026-08-06

### Added
- **Async concurrency helpers** `scrape_many_async` / `scrape_all_async` for running scrapes concurrently with a configurable concurrency cap.
- MCP Toplist rank badge in the README.

### Fixed
- `image_search` returns one consistent result schema across engines (Bing and Google produce the same keys).
- `convert_currency` and `get_weather` docstrings corrected (`wind` → `wind_speed`, right default base/target).

## [1.4.4] - 2026-08-05

### Fixed
- `NewsScraper` returns a `ScrapeError` on a network/transport failure instead of raising.
- `image_search` validates the `engine` argument and raises `ValueError` for an unsupported value instead of silently falling back to Bing.
- MCP `scrape_stock` forwards the `interval` argument (history was locked to daily) and `search_hackernews` forwards the `tags` filter; `scrape_stock`'s mode-default docstring corrected.

## [1.4.3] - 2026-08-04

### Fixed
- Pagination extracts the page number from `offset=` / `start=` / `/p/`-style URLs instead of silently stopping (one regex now drives both detection and extraction).
- The HTTP client is closed before it's rebuilt on retry (no connection leak), and retries re-pick a different proxy from a rotating list.

## [1.4.2] - 2026-08-03

### Fixed
- `GitHubScraper` default `max_results` is now 20, matching the `search_github` MCP tool, so both surface the same number of repositories.
- Multi-valued image attributes (e.g. `srcset`) are coerced to strings, honoring `ImageExtractor`'s `dict[str, str]` contract.

## [1.4.1] - 2026-08-02

### Added
- **Opt-in robots.txt politeness** (`obey_robots`) honoring `Disallow` and `Crawl-delay`, with a per-client, per-User-Agent parser cache.
- **`ScrapeResult.to_csv()` and `.save(path)`** alongside `to_json` / `to_markdown` / `to_dataframe`, with a stdlib fallback that matches the pandas output (incl. empty-data and line-ending handling).

## [1.4.0] - 2026-08-01

### Added
- **Native async scraping across every scraper** (`scrape_async`), built on a real `AsyncHttpClient` rather than a thread pool.
- **Configurable retry/backoff** (`retry_delay`, `backoff_factor`, `backoff_max`), a **response cache TTL** (`cache_ttl`, also settable for the MCP server via `PYSCRAPPY_MCP_CACHE_TTL`), **custom headers / User-Agent override**, and **proxy rotation**.
- **`--json` output** for the `pyscrappy chat` CLI agent, and scheduled (weekly) live integration tests.

## [1.3.1] - 2026-07-28

### Added
- **First-class MCP tools for plugins.** A scraper can set an `mcp_tools` mapping (`tool_name -> method_name`) to be exposed as a dedicated, typed MCP tool instead of only being reachable through the generic `scrape_with`. The tool's input schema is derived from the scraper method's signature, so agents get proper named arguments. Plugins without `mcp_tools` are unaffected.

## [1.3.0] - 2026-07-28

### Added
- **Plugin system.** Scrapers can now be registered and discovered dynamically:
  - `@register_scraper("name")` decorator and `register(name, cls)` for in-process registration.
  - `get_scraper(name)` and `list_scrapers()` to resolve and enumerate scrapers.
  - Automatic discovery of third-party scrapers via the `pyscrappy.scrapers` entry-point group, so an installed `pyscrappy-<name>` package registers itself with no change to PyScrappy core.
  - `BaseScraper` is now exported from the top-level package.
- **Plugin scrapers are agent-ready automatically.** The MCP server exposes two new tools, `list_available_scrapers` and `scrape_with(name, args)`, so any registered scraper (built-in or plugin) is callable by an AI agent and by `pyscrappy chat` without dedicated MCP glue.
- A copyable [`plugin-template/`](plugin-template/) starting point and a plugin authoring guide.

### Changed
- Built-in scrapers are now registered in the shared registry, so the Python API, MCP server, and agent all resolve scrapers through one path.
