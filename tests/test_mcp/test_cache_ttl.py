"""Tests for the MCP server's configurable cache TTL (pyscrappy.mcp.server)."""

import importlib

import pytest

pytest.importorskip("fastmcp")

from pyscrappy.mcp import server  # noqa: E402  (import after the skip guard)


def test_default_ttl_when_env_unset(monkeypatch):
    monkeypatch.delenv("PYSCRAPPY_MCP_CACHE_TTL", raising=False)
    assert server._cache_ttl_from_env() == server._DEFAULT_CACHE_TTL


def test_env_override_is_honored(monkeypatch):
    monkeypatch.setenv("PYSCRAPPY_MCP_CACHE_TTL", "60")
    assert server._cache_ttl_from_env() == 60.0


def test_invalid_env_value_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("PYSCRAPPY_MCP_CACHE_TTL", "not-a-number")
    assert server._cache_ttl_from_env() == server._DEFAULT_CACHE_TTL


def test_non_finite_env_value_falls_back_to_default(monkeypatch):
    for value in ("nan", "inf", "-inf"):
        monkeypatch.setenv("PYSCRAPPY_MCP_CACHE_TTL", value)
        assert server._cache_ttl_from_env() == server._DEFAULT_CACHE_TTL


def test_module_level_ttl_honors_env_var_at_import(monkeypatch):
    """_CACHE_TTL and _config() are set at import time from the env var."""
    monkeypatch.setenv("PYSCRAPPY_MCP_CACHE_TTL", "42")
    try:
        importlib.reload(server)
        assert server._CACHE_TTL == 42.0
        assert server._config().cache_ttl == 42.0
    finally:
        monkeypatch.delenv("PYSCRAPPY_MCP_CACHE_TTL", raising=False)
        importlib.reload(server)
        assert server._CACHE_TTL == server._DEFAULT_CACHE_TTL
