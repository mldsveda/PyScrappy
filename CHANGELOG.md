# Changelog

All notable changes to PyScrappy are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

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
