"""Tests for the Proxlane provider entry in the scraper-API mapping."""

from __future__ import annotations

from pyscrappy.core.scraper_api import build_request, is_configured


def test_proxlane_uses_scraperapi_param_names() -> None:
    endpoint, params = build_request(
        "https://example.com",
        {"provider": "proxlane", "api_key": "KEY", "render_js": True},
    )
    assert params["api_key"] == "KEY"
    assert params["url"] == "https://example.com"
    assert params["render"] == "true"


def test_proxlane_endpoint_can_be_overridden() -> None:
    endpoint, _ = build_request(
        "https://example.com",
        {
            "provider": "proxlane",
            "api_key": "KEY",
            "endpoint": "http://proxlane.local:9000/",
        },
    )
    assert endpoint == "http://proxlane.local:9000/"


def test_proxlane_missing_endpoint_falls_back_to_default() -> None:
    endpoint, _ = build_request(
        "https://example.com",
        {"provider": "proxlane", "api_key": "KEY"},
    )
    assert endpoint == "http://localhost:8000/"


def test_proxlane_is_configured_with_key() -> None:
    assert is_configured({"provider": "proxlane", "api_key": "KEY"})
