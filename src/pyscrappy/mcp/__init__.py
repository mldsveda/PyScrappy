"""PyScrappy MCP server.

Exposes PyScrappy's scrapers as tools over the Model Context Protocol, so an
AI agent (e.g. Claude Desktop) can fetch structured web data.

Run it with::

    pyscrappy-mcp

or::

    python -m pyscrappy.mcp
"""

from pyscrappy.mcp.server import main, mcp

__all__ = ["main", "mcp"]
