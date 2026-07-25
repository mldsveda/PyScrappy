# Dockerfile for the PyScrappy MCP server.
# Builds a container that starts `pyscrappy-mcp` (a stdio MCP server).
FROM python:3.12-slim

WORKDIR /app

# Install PyScrappy with the MCP extra from the local source.
COPY . /app
RUN pip install --no-cache-dir ".[mcp]"

# The MCP server communicates over stdio.
ENTRYPOINT ["pyscrappy-mcp"]
