"""Tests for the `pyscrappy extract` CLI command (URL -> file)."""

from unittest.mock import MagicMock, patch

import pytest

from pyscrappy.cli import run_extract
from pyscrappy.core.models import ScrapeMetadata, ScrapeResult


def _result(data):
    return ScrapeResult(data=data, metadata=ScrapeMetadata(source_urls=["u"], scraper="generic"))


def test_extract_json(tmp_path):
    out = tmp_path / "out.json"
    with patch("pyscrappy.scrape", return_value=_result([{"a": 1}])):
        status = run_extract("http://x", str(out))
    text = out.read_text()
    assert '"a": 1' in text
    assert "wrote" in status and str(out) in status


def test_extract_markdown(tmp_path):
    out = tmp_path / "out.md"
    with patch("pyscrappy.scrape", return_value=_result([{"name": "Alice", "age": "30"}])):
        run_extract("http://x", str(out))
    md = out.read_text()
    assert "Alice" in md  # rendered as markdown, not JSON
    assert "{" not in md


def test_extract_txt_whole_page(tmp_path):
    out = tmp_path / "out.txt"
    data = [{"text": {"text": "hello world", "paragraphs": [], "word_count": 2}}]
    with patch("pyscrappy.scrape", return_value=_result(data)):
        run_extract("http://x", str(out))
    assert out.read_text() == "hello world"


def test_extract_txt_with_css_selector(tmp_path):
    out = tmp_path / "out.txt"
    # With a selector, run_extract passes selectors={"match": ...}; each row's
    # "match" is joined by newline.
    data = [{"match": "one"}, {"match": "two"}]
    with patch("pyscrappy.scrape", return_value=_result(data)) as m:
        run_extract("http://x", str(out), css_selector=".item")
    assert out.read_text() == "one\ntwo"
    assert m.call_args.kwargs["selectors"] == {"match": ".item"}


def test_extract_html_fetches_raw_markup(tmp_path):
    out = tmp_path / "out.html"
    fake_gs = MagicMock()
    fake_gs.__enter__.return_value = fake_gs
    fake_gs.__exit__.return_value = False
    fake_gs.http.get_html.return_value = "<html><body>raw</body></html>"
    with patch("pyscrappy.GenericScraper", return_value=fake_gs):
        run_extract("http://x", str(out))
    assert out.read_text() == "<html><body>raw</body></html>"
    fake_gs.http.get_html.assert_called_once_with("http://x")


def test_extract_rejects_unknown_extension(tmp_path):
    out = tmp_path / "out.pdf"
    with pytest.raises(ValueError, match="unsupported output extension"):
        run_extract("http://x", str(out))
