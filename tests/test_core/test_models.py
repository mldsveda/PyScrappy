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
        pytest.importorskip("pandas")

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

    @pytest.mark.parametrize(
        ("raw_level", "expected_prefix"),
        [
            ("h1", "#"),
            ("H6", "######"),
            ("h0", "#"),
            ("h9", "######"),
            ("title", "##"),
            ("", "##"),
            (None, "##"),
        ],
    )
    def test_to_markdown_handles_nonstandard_heading_levels(self, raw_level, expected_prefix):
        result = ScrapeResult(
            data=[
                {
                    "text": {
                        "text": "body",
                        "headings": [{"level": raw_level, "text": "Heading"}],
                    }
                }
            ]
        )

        assert result.to_markdown().splitlines()[0] == f"{expected_prefix} Heading"

    def test_to_markdown_preserves_late_table_columns(self):
        result = ScrapeResult(
            data=[
                {
                    "text": {"text": "", "headings": []},
                    "tables": [
                        [
                            {"A": "1", "B": "2"},
                            {"A": "3", "B": "4", "column_3": "extra"},
                        ]
                    ],
                }
            ]
        )

        assert result.to_markdown() == (
            "| A | B | column_3 |\n| --- | --- | --- |\n| 1 | 2 |  |\n| 3 | 4 | extra |"
        )

    def test_to_markdown_escapes_table_cells(self):
        result = ScrapeResult(
            data=[
                {
                    "text": {"text": "", "headings": []},
                    "tables": [[{"Name|Path": "Alice|C:\\Users\r\nAdmin"}]],
                }
            ]
        )

        assert result.to_markdown() == (
            "| Name\\|Path |\n| --- |\n| Alice\\|C:\\\\Users<br>Admin |"
        )

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

    def test_to_csv(self):
        result = ScrapeResult(data=[{"name": "a", "price": 1}, {"name": "b", "price": 2}])
        csv_text = result.to_csv()
        assert "name,price" in csv_text.replace(" ", "")
        assert "a,1" in csv_text.replace(" ", "")
        assert "b,2" in csv_text.replace(" ", "")

    def test_to_csv_empty(self):
        assert ScrapeResult(data=[]).to_csv() == ""

    def test_to_csv_stdlib_fallback_without_pandas(self, monkeypatch):
        """Force the stdlib csv path (pandas unavailable) and confirm it produces
        the same header/rows and "\n" line endings as the pandas path."""
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pandas":
                raise ImportError("no pandas")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = ScrapeResult(data=[{"name": "a", "price": 1}, {"name": "b", "price": 2}])
        csv_text = result.to_csv()
        assert csv_text == "name,price\na,1\nb,2\n"  # "\n", not "\r\n"

    def test_save_json_csv_md(self, tmp_path):
        result = ScrapeResult(data=[{"title": "x", "n": 1}])
        json_path = tmp_path / "out.json"
        csv_path = tmp_path / "out.csv"
        md_path = tmp_path / "out.md"
        result.save(str(json_path))
        result.save(str(csv_path))
        result.save(str(md_path))
        assert json.loads(json_path.read_text())["data"] == [{"title": "x", "n": 1}]
        assert "title,n" in csv_path.read_text().replace(" ", "")
        assert "**title:** x" in md_path.read_text()

    def test_save_unsupported_extension(self, tmp_path):
        result = ScrapeResult(data=[{"a": 1}])
        with pytest.raises(ValueError, match="Unsupported extension"):
            result.save(str(tmp_path / "out.txt"))

    # --- to_ndjson --------------------------------------------------------- #

    def test_to_ndjson_round_trip(self):
        result = ScrapeResult(data=[{"name": "a", "v": 1}, {"name": "b", "v": 2}])
        lines = result.to_ndjson().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"name": "a", "v": 1}
        assert json.loads(lines[1]) == {"name": "b", "v": 2}

    def test_to_ndjson_unicode_preserved(self):
        result = ScrapeResult(data=[{"city": "Zurich"}, {"city": "東京"}])
        lines = result.to_ndjson().split("\n")
        parsed = [json.loads(line) for line in lines]
        assert parsed[0]["city"] == "Zurich"
        assert parsed[1]["city"] == "東京"
        # ensure_ascii=False means non-ASCII chars appear literally
        assert "東京" in result.to_ndjson()

    def test_to_ndjson_empty(self):
        assert ScrapeResult(data=[]).to_ndjson() == ""

    # --- to_yaml ----------------------------------------------------------- #

    def test_to_yaml(self):
        pytest.importorskip("yaml")
        import yaml

        result = ScrapeResult(
            data=[{"name": "item1"}],
            metadata=ScrapeMetadata(source_urls=["https://example.com"], scraper="test"),
            errors=[ScrapeError(url="https://example.com", message="warn")],
        )
        parsed = yaml.safe_load(result.to_yaml())
        assert parsed["data"] == [{"name": "item1"}]
        assert parsed["metadata"]["source_urls"] == ["https://example.com"]
        assert parsed["metadata"]["scraper"] == "test"
        assert len(parsed["errors"]) == 1
        assert parsed["errors"][0]["message"] == "warn"

    def test_to_yaml_non_primitive_value_is_safe_load_roundtrippable(self):
        # A non-primitive value in data (e.g. a datetime) must not emit a
        # python-specific tag that yaml.safe_load can't read. It's coerced to a
        # string via the JSON round-trip, so safe_load parses it back cleanly.
        pytest.importorskip("yaml")
        import datetime

        import yaml

        result = ScrapeResult(data=[{"name": "café", "when": datetime.datetime(2026, 1, 2)}])
        out = result.to_yaml()
        assert "!!python" not in out  # no unsafe tags
        parsed = yaml.safe_load(out)  # would raise if unsafe tags were present
        assert parsed["data"][0]["name"] == "café"  # unicode preserved
        assert isinstance(parsed["data"][0]["when"], str)  # datetime -> string

    def test_to_yaml_empty_data(self):
        pytest.importorskip("yaml")
        import yaml

        result = ScrapeResult(data=[])
        parsed = yaml.safe_load(result.to_yaml())
        assert parsed["data"] == []

    def test_to_yaml_missing_pyyaml(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("no yaml")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = ScrapeResult(data=[{"a": 1}])
        with pytest.raises(ImportError, match="PyYAML is required"):
            result.to_yaml()

    # --- save() extensions ------------------------------------------------- #

    def test_save_ndjson_and_jsonl(self, tmp_path):
        result = ScrapeResult(data=[{"x": 1}, {"x": 2}])
        ndjson_path = tmp_path / "out.ndjson"
        jsonl_path = tmp_path / "out.jsonl"
        result.save(str(ndjson_path))
        result.save(str(jsonl_path))
        for path in (ndjson_path, jsonl_path):
            lines = path.read_text().splitlines()
            assert len(lines) == 2
            assert json.loads(lines[0]) == {"x": 1}
            assert json.loads(lines[1]) == {"x": 2}

    def test_save_yaml_and_yml(self, tmp_path):
        pytest.importorskip("yaml")
        import yaml

        result = ScrapeResult(data=[{"a": 1}])
        yaml_path = tmp_path / "out.yaml"
        yml_path = tmp_path / "out.yml"
        result.save(str(yaml_path))
        result.save(str(yml_path))
        for path in (yaml_path, yml_path):
            parsed = yaml.safe_load(path.read_text())
            assert parsed["data"] == [{"a": 1}]

    def test_save_ndjson_empty_data(self, tmp_path):
        result = ScrapeResult(data=[])
        path = tmp_path / "empty.ndjson"
        result.save(str(path))
        assert path.read_text() == ""

    def test_save_creates_parent_directories(self, tmp_path):
        result = ScrapeResult(data=[{"a": 1}])
        nested_path = tmp_path / "nested" / "deeply" / "out.json"
        result.save(str(nested_path))
        assert nested_path.exists()
        assert json.loads(nested_path.read_text())["data"] == [{"a": 1}]

    def test_save_bare_filename(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = ScrapeResult(data=[{"b": 2}])
        result.save("bare_out.json")
        saved = tmp_path / "bare_out.json"
        assert saved.exists()
        assert json.loads(saved.read_text())["data"] == [{"b": 2}]
