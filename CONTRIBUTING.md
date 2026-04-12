# Contributing to PyScrappy

Thank you for your interest in contributing to PyScrappy! We welcome contributions of all kinds — from bug fixes and documentation improvements to new scrapers and core features.

## Checklist before submitting a PR

Here are the core requirements for any PR submitted to PyScrappy:

- [ ] **Keep scope isolated** — your changes should address 1 specific problem at a time
- [ ] **Add tests** — adding at least 1 test is a hard requirement — [see details](#adding-tests)
- [ ] **Ensure your PR passes all checks:**
  - [ ] Unit tests — `pytest tests/ -v`
  - [ ] Linting — `ruff check src/`

## Quick Start

### 1. Setup Your Local Development Environment

```sh
# Fork the repository on GitHub (click the Fork button at https://github.com/mldsveda/PyScrappy)
# Then clone your fork locally
git clone https://github.com/YOUR_USERNAME/PyScrappy.git
cd PyScrappy

# Create a new branch for your feature
git checkout -b your-feature-branch

# Install the package in editable mode with all extras
pip install -e '.[all]'

# Install development tools
pip install pytest ruff mypy

# Verify your setup works
pytest tests/ -v
```

That's it! Your local development environment is ready.

### 2. Development Workflow

Here's the recommended workflow for making changes:

```sh
# Make your changes to the code
# ...

# Run linting to catch issues early
ruff check src/

# Run the full test suite
pytest tests/ -v

# Commit your changes
git add .
git commit -m "Your descriptive commit message"

# Push and create a PR
git push origin your-feature-branch
```

## Adding Tests

Adding at least 1 test is a **hard requirement** for all PRs.

### Where to Add Tests

| What you changed | Where to add tests |
|---|---|
| `src/pyscrappy/core/` | `tests/test_core/` |
| `src/pyscrappy/generic/` | `tests/test_generic/` |
| `src/pyscrappy/scrapers/` | `tests/test_scrapers/` |
| Package-level (`__init__.py`) | `tests/test_init.py` |

### File Naming Convention

The `tests/` directory mirrors the structure of `src/pyscrappy/`:

| Source file | Test file |
|---|---|
| `src/pyscrappy/core/config.py` | `tests/test_core/test_config.py` |
| `src/pyscrappy/core/http.py` | `tests/test_core/test_http.py` |
| `src/pyscrappy/generic/extractors.py` | `tests/test_generic/test_extractors.py` |
| `src/pyscrappy/scrapers/wikipedia.py` | `tests/test_scrapers/test_wikipedia.py` |

### Key Testing Principles

- **Mock HTTP calls** — never make real network requests in tests. Use `unittest.mock.MagicMock` to mock the `_http` attribute on scrapers.
- **Test parsing logic** — provide realistic sample HTML/JSON and verify the scraper extracts the correct fields.
- **Test edge cases** — empty responses, missing fields, malformed HTML.
- **Test validation** — ensure proper errors are raised for invalid arguments.

### Example Test

```python
from unittest.mock import MagicMock
from pyscrappy.scrapers.wikipedia import WikipediaScraper

SAMPLE_HTML = """
<html><body>
<div id="mw-content-text">
<div class="mw-parser-output">
    <p>Python is a high-level programming language.</p>
</div>
</div>
</body></html>
"""

def test_wikipedia_scrape_returns_paragraphs():
    """Test that WikipediaScraper extracts paragraph text."""
    scraper = WikipediaScraper()
    mock_http = MagicMock()
    mock_http.get_html.return_value = SAMPLE_HTML
    scraper._http = mock_http

    result = scraper.scrape(query="Python", mode="paragraphs")

    assert len(result.data) > 0
    assert result.data[0]["type"] == "paragraph"
    assert "Python" in result.data[0]["text"]
    scraper.close()
```

## Running Tests and Checks

### Running Unit Tests

Run the full test suite:

```sh
pytest tests/ -v
```

Run a specific test file:

```sh
pytest tests/test_core/test_http.py -v
```

Run a specific test:

```sh
pytest tests/test_scrapers/test_wikipedia.py::TestWikipediaScraperFull::test_full_mode -v
```

### Running Linting

Run Ruff linting (matches CI):

```sh
ruff check src/
```

Auto-fix linting issues:

```sh
ruff check src/ --fix
```

### Running Type Checks (optional)

```sh
mypy src/pyscrappy/
```

### CI Compatibility

To ensure your changes will pass CI, run the same checks locally:

```sh
# These match the GitHub Actions workflows exactly
ruff check src/
pytest tests/ -v
```

CI runs tests across Python 3.9, 3.11, 3.12, and 3.13.

## Project Structure

```
PyScrappy/
├── src/pyscrappy/
│   ├── __init__.py          # Package exports and convenience scrape() function
│   ├── core/                # Core infrastructure
│   │   ├── base.py          # BaseScraper abstract class
│   │   ├── browser.py       # Playwright browser manager
│   │   ├── config.py        # ScraperConfig dataclass
│   │   ├── exceptions.py    # Custom exception hierarchy
│   │   ├── http.py          # HTTP client with retries/rate-limiting
│   │   └── models.py        # ScrapeResult, ScrapeMetadata, ScrapeError
│   ├── generic/             # GenericScraper (works on any URL)
│   │   ├── scraper.py       # Main GenericScraper class
│   │   ├── extractors.py    # Metadata, Text, Link, Image, Table extractors
│   │   └── pagination.py    # Auto-pagination detection
│   └── scrapers/            # Site-specific scrapers (16 total)
│       ├── wikipedia.py
│       ├── imdb.py
│       ├── stock.py
│       └── ...
├── tests/
│   ├── test_core/           # Tests for core/
│   ├── test_generic/        # Tests for generic/
│   ├── test_scrapers/       # Tests for scrapers/
│   └── test_init.py         # Package-level import tests
└── pyproject.toml           # Build config, dependencies, tool settings
```

## Adding a New Scraper

Want to add support for a new website? Here's how:

### 1. Create the scraper

Create a new file in `src/pyscrappy/scrapers/`, e.g. `mysite.py`:

```python
from __future__ import annotations
from typing import Any
from pyscrappy.core.base import BaseScraper
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult

class MySiteScraper(BaseScraper):
    name = "mysite"

    def scrape(self, query: str, **kwargs: object) -> ScrapeResult:
        url = f"https://mysite.com/search?q={query}"
        soup = self.fetch_and_parse(url)

        items: list[dict[str, Any]] = []
        for card in soup.select(".result-card"):
            items.append({
                "title": card.select_one("h2").get_text(strip=True),
                "url": card.select_one("a")["href"],
            })

        return ScrapeResult(
            data=items,
            metadata=ScrapeMetadata(source_urls=[url], scraper=self.name),
        )
```

### 2. Register the export

Add your scraper to:
- `src/pyscrappy/scrapers/__init__.py`
- `src/pyscrappy/__init__.py` (import + add to `__all__`)

### 3. Add tests

Create `tests/test_scrapers/test_mysite.py` with mock HTML and assertions.

### 4. Submit your PR

## Code Quality Standards

- **Style** — enforced by [Ruff](https://docs.astral.sh/ruff/) with a 100-character line length
- **Type hints** — all public APIs should have type annotations
- **Python version** — must be compatible with Python 3.9+
- **No real HTTP calls in tests** — always mock network requests
- **Match existing patterns** — follow the conventions you see in existing scrapers

## Common Issues and Solutions

### Linting Failures

If `ruff check src/` fails:
- Run `ruff check src/ --fix` to auto-fix most issues
- Check import ordering (Ruff enforces isort-compatible ordering)
- Ensure lines are under 100 characters

### Test Failures

If `pytest tests/ -v` fails:
- Check if you broke existing functionality
- Ensure tests use mocks, not real API calls
- Check test file naming conventions (`test_*.py`)
- Make sure `__init__.py` exists in test directories

### Import Errors

If you get `ModuleNotFoundError: No module named 'pyscrappy'`:
```sh
pip install -e '.[all]'
```

## Submitting Your PR

1. **Push your branch:** `git push origin your-feature-branch`
2. **Create a PR:** go to GitHub and create a pull request against `main`
3. **Fill out the description:** clearly explain what your changes do and why
4. **Wait for CI:** ensure all checks pass (lint, tests across Python versions, build)
5. **Address feedback:** make requested changes and push updates
6. **Merge:** once approved, your PR will be merged!

## Getting Help

If you need help:

- [Create an issue](https://github.com/mldsveda/PyScrappy/issues)
- Check existing [discussions](https://github.com/mldsveda/PyScrappy/issues) for similar questions

## What to Contribute

Looking for ideas? Check out:

- **Bug fixes** — check [open issues](https://github.com/mldsveda/PyScrappy/issues)
- **New scrapers** — add support for a website you use
- **Test coverage** — improve tests for existing scrapers
- **Documentation** — improve docstrings, examples, or guides
- **Core improvements** — better error handling, caching, async support

Thank you for contributing to PyScrappy!
