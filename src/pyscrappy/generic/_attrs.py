"""Shared normalization for HTML attribute values.

BeautifulSoup represents multi-valued attributes (``class``, ``rel``, ``headers``,
…) as a *list*, and single-valued ones as a string. Both the adaptive fingerprint
scorer and the ``::attr()`` selector need the same normalization, so it lives
here rather than one reaching into the other's internals.
"""

from __future__ import annotations

from typing import Any


def attr_to_str(v: Any) -> str:
    """A multi-valued attribute (a list) as a space-joined string; a scalar as-is.

    ``["nav", "active"]`` -> ``"nav active"``; ``"/page"`` -> ``"/page"``.
    """
    return " ".join(v) if isinstance(v, list) else str(v)


def attr_to_list(v: Any) -> list[str]:
    """An attribute value as a list of tokens (empty for a missing value)."""
    if not v:
        return []
    return v if isinstance(v, list) else [v]
