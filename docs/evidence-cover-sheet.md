# Open-Source Contribution & Technical Thought Leadership

**Applicant:** Vedaant Singh
**Endorsing Body Criteria:** Mandatory Criterion, Recognition
**Evidence Type:** Open-Source Library (PyPI) & Published Technical Article (Medium)
**Date:** April 2026

## 1. Purpose

This document presents PyScrappy, an open-source Python library designed, architected, and published by the applicant on the Python Package Index (PyPI). The library addresses a structural gap in the Python data extraction ecosystem and is accompanied by a technical deep-dive published on Medium's Analytics Vidhya publication. Together, they demonstrate the applicant's recognition as a leading talent through high-impact open-source contribution and technical thought leadership that advances the digital technology sector.

## 2. Technical Gap & Engineering Response

**Problem:** The Python ecosystem requires developers to choose between two incompatible scraping paradigms. Lightweight HTTP libraries (`requests`, `urllib`) fail on JavaScript-rendered pages (SPAs built with React, Next.js, Nuxt). Browser-automation frameworks (`Selenium`, `Playwright`) impose >100MB binary dependencies and significant resource overhead on every request, even when the target page is static HTML. No widely adopted library bridges both approaches intelligently, nor normalises output across structurally disparate websites into a unified schema.

Additionally, existing scraping libraries provide no built-in resilience: no retry logic, no per-domain rate limiting, no automatic User-Agent rotation, and no resource lifecycle management. Developers must implement each of these independently, leading to fragile, unmaintainable scraping codebases.

**Engineering Response: Dual-Layer Fetching with Heuristic JS Detection**

The applicant designed a dual-layer architecture that attempts a lightweight `httpx` HTTP fetch first, then evaluates three heuristic conditions to determine whether browser-based rendering is required:

- **Body content threshold:** `len(body_text) < 200` with `len(script_tags) > 3`
- **SPA framework markers:** Presence of `window.__NEXT_DATA__`, `window.__NUXT__`, `ReactDOM.render()` in the first 5,000 characters
- **Empty root container:** `<div id="root">`, `<div id="app">`, or `<div id="__next">` with `< 100` characters of content

This eliminates unnecessary browser overhead on static pages while ensuring JavaScript-heavy sites are rendered correctly — a design choice analogous to the lazy initialisation and cost-optimisation patterns the applicant employs in production systems.

> [DIAGRAM PLACEHOLDER — **Figure 1:** Dual-Layer Fetch Decision Flowchart. A flowchart showing: `HTTP Fetch` → `Heuristic Check (3 conditions)` → Branch: `Static: return HTML` / `JS-Rendered: launch Playwright, render, return HTML`. Style consistent with Zola Analytics diagrams (clean boxes, directional arrows, labelled decision nodes). Place after this paragraph.]

## 3. Architecture & Engineering Choices

The library comprises 30+ modules organised into three layers:

**Engineering Choice: Abstract Base Class Scraper Contract**

All 17 site-specific scrapers and the `GenericScraper` inherit from `BaseScraper(ABC)`, which enforces a uniform `scrape() → ScrapeResult` contract. This provides:

- **Shared infrastructure:** HTTP client, browser manager, and HTML parser available via `self.http`, `self.browser`, `self.parse_html()` — no boilerplate per scraper
- **Context-manager lifecycle:** `__enter__`/`__exit__` protocol ensures browser processes and HTTP connections are always cleaned up, even on exceptions
- **Lazy initialisation:** The `http` and `browser` properties instantiate their clients only on first access, avoiding overhead when unused

**Engineering Choice: Unified Output Schema**

Every scraper returns a `ScrapeResult` dataclass containing `data: list[dict]`, `metadata: ScrapeMetadata`, and `errors: list[ScrapeError]`. This normalises structurally disparate sources (e-commerce product cards, financial OHLCV data, news RSS feeds, social media posts) into a single interface with optional serialisation:

- `result.to_dataframe()` — lazy pandas import; raises `ImportError` with install instructions if pandas is absent
- `result.to_json()` — stdlib-only JSON serialisation
- `result.errors` — non-fatal error tracking enables partial results on multi-page scrapes

**Engineering Choice: Per-Domain Rate Limiting with Exponential Backoff**

The `HttpClient` implements per-domain request throttling using `time.monotonic()` tracking and configurable retry logic:

    delay = retry_delay * (2 ** (attempt - 1))

- **429 responses:** Respects `Retry-After` header value
- **5xx errors:** Retries with exponential backoff
- **4xx errors:** Fails immediately (no retry on client errors)
- **User-Agent rotation:** Random selection from a configurable pool on each request

> [DIAGRAM PLACEHOLDER — **Figure 2:** PyScrappy Layered Architecture. A block diagram showing three layers: `User API Layer` (scrape() function, 17 Scraper classes, GenericScraper) → `Core Layer` (BaseScraper ABC, HttpClient, BrowserManager, ScraperConfig, ScrapeResult) → `Extraction Layer` (MetadataExtractor, TextExtractor, LinkExtractor, ImageExtractor, TableExtractor) → `External Sources` (17 website categories). Style: stacked horizontal blocks with arrows, similar to Figure 1 in the Technical Leadership & Impact Report. Place as a full-width diagram.]

### Technical Scope

| Metric | Value |
|--------|-------|
| Python versions supported | 3.9, 3.10, 3.11, 3.12, 3.13 |
| Site-specific scrapers | 17 (across 6 domains) |
| Core infrastructure modules | 6 (config, HTTP client, browser manager, base class, models, exceptions) |
| Generic extraction engines | 5 (metadata, text, links, images, tables) |
| Pagination strategies | 4 (rel=next, text matching, class heuristics, numbered URL patterns) |
| Architecture patterns | ABC inheritance, context managers, lazy initialisation, composition, dataclass configuration |

### Scraper Coverage

| Domain | Scrapers | Approach |
|--------|----------|----------|
| **E-Commerce** | Alibaba, Amazon, Flipkart, Snapdeal | HTTP + CSS selectors |
| **Social Media** | YouTube, Instagram, Twitter/X | Embedded JSON extraction + browser fallback |
| **Music** | Spotify, SoundCloud | Hydration JSON + browser fallback |
| **Food Delivery** | Swiggy, Zomato | Next.js JSON extraction + browser fallback |
| **Data / Research** | Wikipedia, IMDB, Yahoo Finance, News (RSS), Image Search, LinkedIn Jobs | HTTP + structured parsing / JSON API |

## 4. Distribution, Adoption & Maintenance

**Public Distribution**

- **PyPI:** Published at `https://pypi.org/project/PyScrappy/`, installable via `pip install pyscrappy`
- **Total Downloads:** [INSERT TOTAL DOWNLOAD COUNT FROM PePy] downloads to date
- **GitHub:** Public repository at `https://github.com/mldsveda/PyScrappy`
- **GitHub Stars:** [INSERT STAR COUNT] | **Forks:** [INSERT FORK COUNT]

**Active Maintenance**

- **Versioning:** Semantic versioning (v1.0.0), modern `pyproject.toml` packaging (PEP 621)
- **CI/CD:** GitHub Actions pipelines for automated linting (`ruff`), testing (`pytest` across Python 3.9–3.13), package building, and PyPI publishing on release
- **Type Safety:** Full type hints with `py.typed` PEP 561 marker for downstream consumers

> [SCREENSHOT PLACEHOLDER — **Page 2, upper half:** PyPI download statistics from pepy.tech showing download trend graph over time. This demonstrates organic community adoption.]

> [SCREENSHOT PLACEHOLDER — **Page 2, lower half:** GitHub repository header showing stars, forks, commit frequency, and contributor activity. This demonstrates active public maintenance.]

## 5. Technical Thought Leadership

The applicant published an in-depth technical article explaining the design decisions, scraping patterns, and anti-detection logic within PyScrappy:

> **"Web Scraping in Python Using the All-New PyScrappy"**
> Published on **Analytics Vidhya** (Medium), a recognised data science and engineering publication
> URL: `https://medium.com/analytics-vidhya/web-scraping-in-python-using-the-all-new-pyscrappy-5c136ed6906b`
> **Readership:** [INSERT VIEW COUNT] views | [INSERT CLAP COUNT] claps

The article goes beyond surface-level documentation by sharing production-grade technical logic with the developer community:

- **Dual-layer fetching strategy:** Explaining the heuristic conditions under which the system falls back from HTTP to browser rendering
- **Rate-limiting and anti-detection:** Detailing the per-domain throttling algorithm, User-Agent rotation, and exponential-backoff retry mechanism
- **Data normalisation:** Explaining how the unified `ScrapeResult` schema normalises structurally different websites into a consistent format for downstream analysis
- **Modular architecture design:** Walking readers through the ABC pattern, composition-based extractors, and separation of HTTP/browser concerns

The article was editorially reviewed and published under the **Analytics Vidhya** publication, providing independent validation of the content's technical quality. This constitutes peer-reviewed technical education that elevates the community's understanding of maintainable library architecture.

> [SCREENSHOT PLACEHOLDER — **Page 3, upper half:** Medium article header showing the applicant's name, Analytics Vidhya publication badge, publication date, and engagement metrics (views/claps).]

> [SCREENSHOT PLACEHOLDER — **Page 3, lower half:** The most technical section of the article — ideally a code walkthrough or architecture explanation showing the dual-layer fetching logic or the BaseScraper pattern. This proves the content is substantive technical education, not surface-level blogging.]

## 6. Validation

This project demonstrates the applicant's commitment to advancing the digital technology sector through shared tooling and peer-reviewed technical content. The combination of a publicly distributed, production-grade open-source library — solving a genuine architectural gap in the Python ecosystem — with a technical deep-dive published on a recognised data science platform constitutes strong evidence of recognition as a leading talent, evidenced by community adoption (downloads, stars) and by the applicant's contribution to elevating peers through detailed technical education.

---

### Assembly Guide: 3-Page Evidence Document

| Page | Content | What to Add |
|------|---------|-------------|
| **Page 1** | This cover sheet (Sections 1–6) | Replace `[INSERT ...]` placeholders with actual numbers. Create **Figure 1** (fetch flowchart) and **Figure 2** (architecture diagram) matching Zola Analytics visual style. |
| **Page 2** | Distribution & Adoption Proof | **Upper half:** PePy download trend graph (screenshot from pepy.tech/project/pyscrappy). **Lower half:** GitHub repository header screenshot showing stars, forks, languages, and recent commit activity. |
| **Page 3** | Thought Leadership Proof | **Upper half:** Medium article header screenshot (author, publication, date, claps/views). **Lower half:** Excerpt of the most technical section of the article (code block or architecture diagram from the article itself). |

### Diagram Specifications

| Diagram | Where | Style Reference | Content |
|---------|-------|-----------------|---------|
| **Figure 1:** Dual-Layer Fetch Decision Flowchart | Page 1, after Section 2 | Similar to Figure 1 in Technical Innovation & R&D Case Study (Hybrid Search Logic) | `HTTP Fetch` → `Heuristic Evaluation` → `body_text < 200?` / `SPA markers?` / `empty root div?` → Branch to `Return HTML` or `Launch Playwright → Render → Return HTML` |
| **Figure 2:** PyScrappy Layered Architecture | Page 1, after Section 3 | Similar to Figure 2 in Technical Innovation & R&D Case Study (Push-RAG flywheel) | Three-layer stack: User API (scrape(), 17 scrapers) → Core (BaseScraper, HttpClient, BrowserManager, Config, Models) → Extractors (Metadata, Text, Links, Images, Tables) → External (6 domain categories) |
