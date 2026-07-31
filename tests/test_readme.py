from pathlib import Path


def test_readme_documents_mcp_runtime_requirements_and_transports():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    assert "pip install 'pyscrappy[mcp]'" in readme
    assert "standalone `fastmcp` package" in normalized
    assert "requires Python 3.10 or newer" in normalized
    assert "On Python 3.9 the core scraping library still works" in normalized
    assert "pyscrappy-mcp          # stdio (default)" in readme
    assert "pyscrappy-mcp --http   # Streamable HTTP" in readme
    assert "pyscrappy-mcp --sse    # legacy SSE" in readme
