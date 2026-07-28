# PyScrappy plugin template

A minimal, copyable starting point for a PyScrappy scraper plugin. Once
installed, your scraper is available through PyScrappy's Python API, its MCP
server, and the `pyscrappy chat` agent — with no change to PyScrappy core.

## Use it

1. Copy this directory and rename it to your plugin, e.g. `pyscrappy-reddit`.
2. Rename the package folder `pyscrappy_example/` → `pyscrappy_reddit/`.
3. In `pyproject.toml`, update `name`, the `[tool.hatch.build...]` package, and
   the entry point:

   ```toml
   [project.entry-points."pyscrappy.scrapers"]
   reddit = "pyscrappy_reddit:RedditScraper"
   ```

4. Implement your scraper in the package's `__init__.py` (subclass
   `BaseScraper`, set `name`, implement `scrape`).
5. Install and test:

   ```bash
   pip install -e .
   pytest
   ```

## How discovery works

The `[project.entry-points."pyscrappy.scrapers"]` table is what PyScrappy reads.
The key (`example`) is the name used with `get_scraper("example")` and the
`scrape_with` MCP tool; the value points at your class. Nothing else is needed —
PyScrappy discovers installed plugins automatically.

## Using your scraper

```python
from pyscrappy import get_scraper

with get_scraper("example")() as s:
    result = s.scrape(url="https://example.com")
    print(result.to_markdown())
```

From an AI agent (once PyScrappy's MCP server is running): the agent calls
`list_available_scrapers`, sees `example`, and runs it via
`scrape_with(name="example", args={"url": "..."})`.

## Publishing

Build and publish like any Python package (`uv build` / `python -m build`, then
`twine upload`). Name it `pyscrappy-<thing>` so users can find it. Once it's on
PyPI, `pip install pyscrappy-<thing>` is all anyone needs.
