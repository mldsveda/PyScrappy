"""Tests for the scraper registry and plugin discovery."""

import pytest

from pyscrappy import BaseScraper, get_scraper, list_scrapers, register, register_scraper, registry
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult


class _Dummy(BaseScraper):
    name = "dummy"

    def scrape(self, **kwargs):
        return ScrapeResult(data=[{"ok": True}], metadata=ScrapeMetadata(scraper="dummy"))


def test_builtins_are_registered():
    scrapers = list_scrapers()
    # A representative sample of built-ins should be present.
    for name in ("wikipedia", "github", "generic", "stock"):
        assert name in scrapers
    assert get_scraper("wikipedia").__name__ == "WikipediaScraper"


def test_register_imperative():
    register("dummy_imperative", _Dummy)
    assert get_scraper("dummy_imperative") is _Dummy


def test_register_decorator_sets_name():
    @register_scraper("decorated")
    class Decorated(BaseScraper):
        def scrape(self, **kwargs):
            return ScrapeResult(data=[])

    assert get_scraper("decorated") is Decorated
    # decorator fills in .name when not explicitly set
    assert Decorated.name == "decorated"


def test_decorator_keeps_explicit_name():
    @register_scraper("regkey")
    class Explicit(BaseScraper):
        name = "explicit-name"

        def scrape(self, **kwargs):
            return ScrapeResult(data=[])

    # registry key is the decorator arg; class keeps its own name
    assert get_scraper("regkey") is Explicit
    assert Explicit.name == "explicit-name"


def test_unknown_scraper_raises_with_available_names():
    with pytest.raises(KeyError) as exc:
        get_scraper("no-such-scraper")
    assert "no-such-scraper" in str(exc.value)
    assert "Available" in str(exc.value)


def test_entry_point_discovery(monkeypatch):
    """A scraper advertised via an entry point is discovered lazily."""

    class FakeEP:
        name = "fakeplugin"

        def load(self):
            return _Dummy

    # Force rediscovery and inject a fake entry point.
    monkeypatch.setattr(registry, "_entry_points_loaded", False)
    monkeypatch.setattr(registry, "_load_entry_points", _make_loader([FakeEP()]))

    assert get_scraper("fakeplugin") is _Dummy


def test_broken_plugin_is_skipped(monkeypatch):
    """A plugin that fails to load must not break discovery of others."""

    class GoodEP:
        name = "goodplugin"

        def load(self):
            return _Dummy

    class BadEP:
        name = "badplugin"

        def load(self):
            raise ImportError("boom")

    monkeypatch.setattr(registry, "_entry_points_loaded", False)
    monkeypatch.setattr(registry, "_load_entry_points", _make_loader([BadEP(), GoodEP()]))

    scrapers = list_scrapers()
    assert "goodplugin" in scrapers
    assert "badplugin" not in scrapers


def _make_loader(eps):
    """Build a replacement _load_entry_points that registers the given eps."""

    def loader():
        for ep in eps:
            try:
                cls = ep.load()
            except Exception:
                continue
            registry._registry.setdefault(ep.name, cls)

    return loader
