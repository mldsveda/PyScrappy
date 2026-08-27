# Changelog

All notable changes to PyScrappy are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.6.1] - 2026-08-27

### Added
- **Parquet and Excel exporters.** `ScrapeResult.to_parquet(path)` (pandas + pyarrow) and `ScrapeResult.to_excel(path)` (pandas + openpyxl) write results to those formats, and `save()` dispatches `.parquet` / `.xlsx` by extension. Installed via the new `pyscrappy[parquet]` / `pyscrappy[excel]` extras; a missing dependency raises a clear `ImportError` naming the extra to install (#161).

### Fixed
- **On-disk response cache is now bounded.** `_DiskCache.put()` prunes after every write — sweeping expired entries (so a key that is never re-requested no longer lingers, unlike `get()`'s lazy expiry) and then trimming the oldest by mtime past `ScraperConfig.cache_dir_max_size` (default 512, mirroring the in-memory `cache_max_size`). Previously a `cache_dir` grew one file per distinct URL forever (#166).

## [1.6.0] - 2026-08-25

### Fixed
- **`::attr()` normalizes multi-valued attributes.** `css("a::attr(class)")` (and other list-valued attributes like `rel`) now return a space-joined string (`"nav active"`) instead of a Python list repr (`"['nav', 'active']"`); single-valued attributes are unchanged (#167).
- **`to_markdown()` preserves ragged table cells.** Table columns are now the union of keys across all rows (first-seen order), so surplus cells in ragged tables — which `TableExtractor` keeps under `column_N` keys — are no longer dropped from the rendered Markdown (#168).
- **`to_markdown()` no longer crashes on a malformed heading level.** A heading whose `level` isn't `h1`-`h6` (e.g. from user-supplied `data`) now falls back to a default and is clamped into range, instead of raising `ValueError` (#176).

### Changed
- Attribute-normalization helpers moved to a shared `pyscrappy.generic._attrs` module, so the selector no longer imports a private helper out of the adaptive module (internal cleanup; no API change).

## [1.5.9] - 2026-08-25

### Added
- **Observability hooks.** `ScraperConfig` accepts optional `on_request(url)`, `on_retry(url, attempt, delay, error)`, and `on_cache_hit(url)` callbacks, invoked at the corresponding points in both the sync and async HTTP clients — for progress bars/metrics on long crawls without enabling logging. Best-effort: a callback that raises is logged at debug and never breaks the request (#162).

### Fixed
- **Async rate limiting now holds under concurrency.** `AsyncHttpClient._rate_limit` guards its read-compute-write with a per-domain `asyncio.Lock` held across the sleep, so concurrent requests to the same domain on one shared client are spaced by the configured `rate_limit` instead of racing on the same stale timestamp and firing together (#169).

## [1.5.8] - 2026-08-25

### Added
- **Sitemap crawling.** `GenericScraper.sitemap_urls(url)` enumerates a site's page URLs from its `sitemap.xml` (discovered via `robots.txt` `Sitemap:` directives, else the conventional path), following a `<sitemapindex>` one level into its child sitemaps and handling gzip-compressed sitemaps. `GenericScraper.scrape_sitemap(url, max_urls=...)` fetches and extracts every listed page concurrently (via `scrape_all`) into one `ScrapeResult` (#160).

### Changed
- **Retry backoff uses full jitter by default.** Concurrent failures now spread each exponential retry across the interval from zero to its capped delay instead of retrying in lockstep. Set `ScraperConfig(retry_jitter=False)` to preserve the deterministic schedule; explicit server `Retry-After` values remain unchanged (#163).

## [1.5.7] - 2026-08-23

### Added
- **TLS-fingerprint impersonation on the async path.** `ScraperConfig(impersonate=...)` now works with the async client (`AsyncHttpClient` / `scrape_async`), backed by `curl_cffi`'s `AsyncSession`, instead of raising `NotImplementedError`. Stealth and high-throughput async scraping can finally be combined.
- **Optional on-disk response cache.** Set `ScraperConfig(cache_dir=...)` (with `cache_ttl > 0`) to persist successful GETs to disk, so cache hits survive process restarts and separate runs. The in-memory LRU cache still fronts it; a disk hit is promoted back into memory.
- **`AdaptiveStore.heal_report()`** — aggregates the heal audit log into one row per selector (heal count, latest/lowest/average confidence, last-healed time), sorted most-healed first, so the most-drifted selectors and shakiest relocations surface for review.

## [1.5.6] - 2026-08-19

### Fixed
- **robots.txt server errors now fail closed.** A `5xx` (or a connection error / timeout) while fetching `robots.txt` is treated as disallow-all and is *not* cached, so a later request re-fetches — instead of the previous behavior of parsing an empty body as allow-all and caching that for the session. `4xx` (e.g. a missing `robots.txt`) still means allow-all, and `2xx` rules are unchanged. Sync and async paths are kept in lockstep (#152).
- **Offset-based pagination advances by the page size, not by 1.** For `offset=`/`start=` URLs, `find_next_page_url` now infers the step from the gaps between the page links (e.g. `0/20/40/60` → `+20`) instead of `+1`, which silently under-collected on offset-paginated sites. `page`/`p` URLs still advance by 1 (#151).
- **`ScrapeResult.save()` creates parent directories.** Saving to a path whose directory does not exist (e.g. `out/nested/data.json`) now creates the directory tree instead of raising `FileNotFoundError` (#150).

## [1.5.5] - 2026-08-17

### Added
- **Semantic contract on adaptive heals.** `Selector.css(..., expect=<callable>)` requires a relocated element to satisfy a caller-supplied invariant (e.g. text looks like a price); a heal that clears the structural threshold but fails the contract is rejected, so structural similarity alone can't redefine what a field means.
- **Heal audit log.** Every accepted heal is appended to an append-only NDJSON log beside the fingerprint store (`adaptive.heal.ndjson`), recording confidence, runner-up gap, and the before/after fingerprint. Read it via `AdaptiveStore.heal_log(identifier=None, namespace=None)` so selector drift stays observable.
- **`cache_max_size` config field** (default `512`). The in-memory response cache is now LRU-bounded, so a long-running process (e.g. the MCP server) that fetches many distinct URLs no longer grows without limit.

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
