"""MCP tools must advertise only engines the scrapers actually support."""

from __future__ import annotations

import pytest

pytest.importorskip("fastmcp")

from pyscrappy.mcp import server  # noqa: E402


def test_search_images_doc_does_not_advertise_duckduckgo():
    doc = server.search_images.__doc__ or ""
    assert "duckduckgo" not in doc.lower()
    assert "bing" in doc.lower()
    assert "google" in doc.lower()
