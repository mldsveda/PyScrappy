"""Scraper registry and plugin discovery.

PyScrappy scrapers can come from three places, all landing in one registry:

1. Built-in scrapers shipped in this package.
2. Third-party packages that declare a ``pyscrappy.scrapers`` entry point.
3. In-process registration via the :func:`register_scraper` decorator.

External packages register a scraper by adding to their ``pyproject.toml``::

    [project.entry-points."pyscrappy.scrapers"]
    reddit = "pyscrappy_reddit:RedditScraper"

Once the package is installed, ``get_scraper("reddit")`` resolves it and the MCP
server / ``pyscrappy chat`` agent expose it as a tool automatically — no change
to PyScrappy core required.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from pyscrappy.core.base import BaseScraper

ENTRY_POINT_GROUP = "pyscrappy.scrapers"

_S = TypeVar("_S", bound="type[BaseScraper]")

# name -> scraper class. Populated lazily: entry points are discovered on first
# access so importing pyscrappy stays fast.
_registry: dict[str, type[BaseScraper]] = {}
_entry_points_loaded = False


def register_scraper(name: str) -> Callable[[_S], _S]:
    """Register a scraper class under ``name``.

    Usage::

        from pyscrappy import BaseScraper, register_scraper

        @register_scraper("reddit")
        class RedditScraper(BaseScraper):
            name = "reddit"
            def scrape(self, **kwargs): ...

    The decorator sets ``cls.name`` if it isn't already set, so the class attr
    and the registry key stay in sync.
    """

    def decorator(cls: _S) -> _S:
        if not getattr(cls, "name", None) or cls.name == "base":
            cls.name = name
        _registry[name] = cls
        return cls

    return decorator


def register(name: str, cls: type[BaseScraper]) -> None:
    """Register a scraper class imperatively (non-decorator form)."""
    _registry[name] = cls


def _load_entry_points() -> None:
    """Discover scrapers advertised by installed packages via entry points."""
    global _entry_points_loaded
    if _entry_points_loaded:
        return
    _entry_points_loaded = True

    from importlib import metadata

    # The entry_points() API changed in 3.10; support both.
    if sys.version_info >= (3, 10):
        eps = metadata.entry_points(group=ENTRY_POINT_GROUP)
    else:  # pragma: no cover - exercised only on 3.9
        eps = metadata.entry_points().get(ENTRY_POINT_GROUP, [])

    for ep in eps:
        # A broken third-party plugin must not take down the whole registry.
        try:
            cls = ep.load()
        except Exception:  # noqa: BLE001 - defensive: skip unloadable plugins
            continue
        # Don't let a plugin clobber a name already registered in-process.
        _registry.setdefault(ep.name, cls)


def get_scraper(name: str) -> type[BaseScraper]:
    """Return the scraper class registered under ``name``.

    Raises:
        KeyError: if no scraper is registered under that name.
    """
    _load_entry_points()
    try:
        return _registry[name]
    except KeyError:
        raise KeyError(
            f"No scraper registered under {name!r}. "
            f"Available: {', '.join(sorted(_registry)) or '(none)'}"
        ) from None


def list_scrapers() -> dict[str, type[BaseScraper]]:
    """Return a copy of the full registry (built-ins + plugins), name -> class."""
    _load_entry_points()
    return dict(_registry)
