"""Tests for pyscrappy.core.models."""

import json

import pytest

from pyscrappy.core.models import ScrapeError, ScrapeMetadata, ScrapeResult


class TestScrapeError:
    def test_basic_fields(self):
        err = ScrapeError(url="https://example.com", message="not found")
        assert err.url == "https://example.com"
        assert err.message == "not found"
        assert err.selector is None

    def test_with_selector(self):
        err = ScrapeError(url="https://x.com", message="empty", selector="div.content")
        assert err.selector == "div.content"


class TestScrapeMetadata:
    def test_defaults(self):
        meta = ScrapeMetadata()
        assert meta.source_urls == []
        assert meta.total_pages == 1
        assert meta.scraper == ""
        assert meta.timestamp  # non-empty ISO string

    def test_timestamp_is_iso_format(self):
        meta = ScrapeMetadata()
        # Should be parseable as ISO datetime
        from datetime import datetime
        dt = datetime.fromisoformat(meta.timestamp)
        assert dt is not None

    def test_custom_values(self):
        meta = ScrapeMetadata(
            source_urls=["https://a.com", "https://b.com"],
            total_pages=2,
            scraper="test_scraper",
        )
        assert len(meta.source_urls) == 2
        assert meta.total_pages == 2
        assert meta.scraper == "test_scraper"


class TestScrapeResult:
    def test_empty_result(self):
        result = ScrapeResult(data=[])
        assert len(result) == 0
        assert bool(result) is False

    def test_result_with_data(self):
        result = ScrapeResult(data=[{"title": "test"}, {"title": "test2"}])
        assert len(result) == 2
        assert bool(result) is True

    def test_default_metadata_and_errors(self):
        result = ScrapeResult(data=[{"a": 1}])
        assert isinstance(result.metadata, ScrapeMetadata)
        assert result.errors == []

    def test_to_json(self):
        result = ScrapeResult(
            data=[{"name": "item1", "price": 10}],
            metadata=ScrapeMetadata(
                source_urls=["https://example.com"],
                total_pages=1,
                scraper="test",
            ),
            errors=[ScrapeError(url="https://example.com", message="warning")],
        )
        json_str = result.to_json()
        parsed = json.loads(json_str)

        assert parsed["data"] == [{"name": "item1", "price": 10}]
        assert parsed["metadata"]["source_urls"] == ["https://example.com"]
        assert parsed["metadata"]["total_pages"] == 1
        assert parsed["metadata"]["scraper"] == "test"
        assert len(parsed["errors"]) == 1
        assert parsed["errors"][0]["message"] == "warning"

    def test_to_json_indent(self):
        result = ScrapeResult(data=[{"x": 1}])
        json_4 = result.to_json(indent=4)
        # 4-space indent should be present
        assert "    " in json_4

    def test_to_json_empty(self):
        result = ScrapeResult(data=[])
        parsed = json.loads(result.to_json())
        assert parsed["data"] == []
        assert parsed["errors"] == []

    def test_to_dataframe_missing_pandas(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pandas":
                raise ImportError("no pandas")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = ScrapeResult(data=[{"a": 1}])
        with pytest.raises(ImportError, match="pandas is required"):
            result.to_dataframe()

    def test_to_dataframe_with_pandas(self):
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        result = ScrapeResult(data=[{"a": 1, "b": 2}, {"a": 3, "b": 4}])
        df = result.to_dataframe()
        assert len(df) == 2
        assert list(df.columns) == ["a", "b"]

    def test_to_markdown_flat_item(self):
        result = ScrapeResult(data=[{"title": "Inception", "year": "2010", "rating": "8.8"}])
        md = result.to_markdown()
        assert "**title:** Inception" in md
        assert "**year:** 2010" in md
        assert "**rating:** 8.8" in md

    def test_to_markdown_rich_item(self):
        result = ScrapeResult(
            data=[
                {
                    "url": "https://example.com",
                    "metadata": {"title": "Web scraping"},
                    "text": {
                        "text": "Web scraping is the extraction of data.",
                        "headings": [{"level": "h2", "text": "Overview"}],
                    },
                    "tables": [[{"Name": "Alice", "Age": "30"}]],
                }
            ]
        )
        md = result.to_markdown()
        assert "# Web scraping" in md
        assert "## Overview" in md
        assert "Web scraping is the extraction of data." in md
        assert "| Name | Age |" in md
        assert "| Alice | 30 |" in md

    def test_to_markdown_separates_items(self):
        result = ScrapeResult(data=[{"a": "1"}, {"a": "2"}])
        assert "\n\n---\n\n" in result.to_markdown()

    def test_to_markdown_empty(self):
        assert ScrapeResult(data=[]).to_markdown() == ""

    def test_errors_list(self):
        errors = [
            ScrapeError(url="https://a.com", message="err1"),
            ScrapeError(url="https://b.com", message="err2", selector=".x"),
        ]
        result = ScrapeResult(data=[], errors=errors)
        assert len(result.errors) == 2
        assert result.errors[1].selector == ".x"
