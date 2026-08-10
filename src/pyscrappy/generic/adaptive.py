"""Adaptive (self-healing) element relocation.

When a site changes its markup, a hard-coded CSS selector silently breaks. An
adaptive selector remembers a *fingerprint* of the element it matched, and when
the selector later returns nothing, relocates the element by scoring every
candidate in the new page against that fingerprint.

This is our own design (informed by prior art, not copied). It differs on four
points that matter in practice:

1. **Weighted signals, not a flat average.** A stable ``id`` / ``data-*`` hook is
   far stronger evidence than a sibling-tag list, so signals are weighted by how
   stable they tend to be. Weak signals can't dilute strong ones.
2. **Anchor-relative fingerprints.** Besides the absolute ancestor path, the
   fingerprint records the nearest *stable* ancestor (one with an id or a
   ``data-*`` attribute) and the depth to it, so relocation survives layout
   reshuffles that shift absolute positions.
3. **Volatility-aware text.** Text that looks volatile (prices, counts, dates) is
   down-weighted, so relocation stays robust on exactly the fields that change
   most between scrapes.
4. **Pruning before scoring.** Candidates are cheaply filtered by tag before the
   expensive per-node similarity, so it scales to large pages.

The scorer returns a :class:`MatchResult` carrying the confidence and the gap to
the runner-up, so callers can tell a clean match from an ambiguous one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from bs4 import Tag

# Text that changes between scrapes shouldn't anchor an element. A cell that is
# mostly digits / currency / date-like is treated as volatile and down-weighted.
_VOLATILE = re.compile(
    r"""^[\s]*(
        [$€£¥₹]?\s*[\d,.]+\s*[%$€£¥₹]?      # prices, percentages, plain numbers
        | \d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}   # dates
        | \d+\s*(min|sec|hour|day|week|month|year)s?  # durations
    )[\s]*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Attributes that make a good stable anchor when present on an ancestor.
_STABLE_ATTRS = ("id", "data-testid", "data-test", "data-id", "data-qa")

# Per-signal weights. Higher = stronger evidence of identity. These are the
# heart of "weighted, not averaged": id/data hooks dominate, volatile text barely
# counts. Tuned so a single strong hook can carry a match through heavy churn.
_WEIGHTS = {
    "tag": 1.0,
    "id": 6.0,
    "stable_attr": 5.0,  # data-testid / data-test / etc. on the element
    "class": 2.5,
    "other_attrs": 1.5,
    "text_stable": 3.5,
    "text_volatile": 0.3,
    "anchor": 3.0,  # nearest stable ancestor + depth
    "path": 1.0,
    "siblings": 0.5,
}


def _text_is_volatile(text: str | None) -> bool:
    return bool(text and _VOLATILE.match(text))


def fingerprint(el: Tag) -> dict[str, Any]:
    """Capture the identifying features of ``el`` as a JSON-serializable dict."""
    attrs = {k: _attr_str(v) for k, v in (el.attrs or {}).items()}
    text = el.get_text(strip=True) or None
    anchor_tag, anchor_id, anchor_depth = _nearest_stable_anchor(el)
    return {
        "tag": el.name,
        "id": attrs.get("id"),
        "stable_attr": _first_stable_attr(attrs),
        "classes": sorted(_attr_list(el.get("class"))),
        "attrs": {k: v for k, v in attrs.items() if k not in ("id", "class")},
        "text": text,
        "text_volatile": _text_is_volatile(text),
        "path": _ancestor_path(el),
        "anchor_tag": anchor_tag,
        "anchor_id": anchor_id,
        "anchor_depth": anchor_depth,
        "siblings": _sibling_tags(el),
    }


def _attr_str(v: Any) -> str:
    return " ".join(v) if isinstance(v, list) else str(v)


def _attr_list(v: Any) -> list[str]:
    if not v:
        return []
    return v if isinstance(v, list) else [v]


def _first_stable_attr(attrs: dict[str, str]) -> str | None:
    for name in _STABLE_ATTRS:
        if name != "id" and attrs.get(name):
            return f"{name}={attrs[name]}"
    return None


def _ancestor_path(el: Tag) -> list[str]:
    path = []
    node: Tag | None = el
    while isinstance(node, Tag):
        path.append(node.name)
        node = node.parent
    return list(reversed(path))


def _sibling_tags(el: Tag) -> list[str]:
    parent = el.parent
    if not isinstance(parent, Tag):
        return []
    return [c.name for c in parent.find_all(recursive=False) if c is not el]


def _nearest_stable_anchor(el: Tag) -> tuple[str | None, str | None, int]:
    """Walk up to the nearest ancestor carrying a stable hook (id / data-*).
    Returns (ancestor_tag, anchor_value, depth) or (None, None, -1)."""
    depth = 0
    node = el.parent
    while isinstance(node, Tag):
        depth += 1
        if node.get("id"):
            return node.name, f"id={node.get('id')}", depth
        for name in _STABLE_ATTRS:
            if name != "id" and node.get(name):
                return node.name, f"{name}={node.get(name)}", depth
        node = node.parent
    return None, None, -1


def _ratio(a: Any, b: Any) -> float:
    return SequenceMatcher(None, a or "", b or "").ratio()


@dataclass
class MatchResult:
    """A relocation result: the chosen element, its confidence (0-100), and the
    gap to the next-best candidate (a large gap means an unambiguous match)."""

    element: Tag | None
    confidence: float
    runner_up_gap: float
    considered: int = 0
    scored: int = 0


@dataclass
class _Scored:
    el: Tag
    score: float
    weight: float = field(default=0.0)


def _score(fp: dict[str, Any], cand: Tag) -> float:
    """Weighted similarity of a candidate to a stored fingerprint, 0-100.

    Each contributing signal adds ``weight * signal_ratio`` to the numerator and
    ``weight`` to the denominator, so the result is a weight-normalized percentage
    — strong signals (id/data hooks) pull far harder than weak ones (siblings).
    """
    cfp = fingerprint(cand)
    num = 0.0
    den = 0.0

    def add(weight: float, ratio: float) -> None:
        nonlocal num, den
        num += weight * ratio
        den += weight

    add(_WEIGHTS["tag"], 1.0 if fp["tag"] == cfp["tag"] else 0.0)

    if fp["id"]:
        add(_WEIGHTS["id"], _ratio(fp["id"], cfp["id"]))
    if fp["stable_attr"]:
        add(_WEIGHTS["stable_attr"], _ratio(fp["stable_attr"], cfp["stable_attr"]))

    if fp["classes"] or cfp["classes"]:
        add(_WEIGHTS["class"], _jaccard(fp["classes"], cfp["classes"]))

    if fp["attrs"] or cfp["attrs"]:
        add(_WEIGHTS["other_attrs"], _dict_ratio(fp["attrs"], cfp["attrs"]))

    if fp["text"]:
        # Volatile text (prices/dates/counts) barely counts; stable text anchors.
        weight = _WEIGHTS["text_volatile"] if fp["text_volatile"] else _WEIGHTS["text_stable"]
        add(weight, _ratio(fp["text"], cfp["text"]))

    # Anchor-relative: reward sharing the same nearest stable ancestor at a
    # similar depth. Survives absolute-path reshuffles.
    if fp["anchor_id"]:
        anchor_ratio = _ratio(fp["anchor_id"], cfp["anchor_id"])
        if fp["anchor_tag"] == cfp["anchor_tag"] and cfp["anchor_id"]:
            depth_penalty = 1.0 / (1 + abs(fp["anchor_depth"] - cfp["anchor_depth"]))
            anchor_ratio = (anchor_ratio + depth_penalty) / 2
        add(_WEIGHTS["anchor"], anchor_ratio)

    add(_WEIGHTS["path"], _ratio("/".join(fp["path"]), "/".join(cfp["path"])))

    if fp["siblings"] or cfp["siblings"]:
        add(_WEIGHTS["siblings"], _ratio("/".join(fp["siblings"]), "/".join(cfp["siblings"])))

    return round((num / den) * 100, 2) if den else 0.0


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _dict_ratio(a: dict[str, str], b: dict[str, str]) -> float:
    keys = _jaccard(list(a), list(b))
    shared = set(a) & set(b)
    vals = sum(_ratio(a[k], b[k]) for k in shared) / len(shared) if shared else 0.0
    return (keys + vals) / 2


def relocate(fp: dict[str, Any], root: Tag, threshold: float = 55.0) -> MatchResult:
    """Find the element in ``root`` that best matches the stored fingerprint.

    Candidates are pruned to the fingerprint's tag first (cheap), then scored.
    Returns a :class:`MatchResult`; ``element`` is None if nothing clears
    ``threshold``. ``runner_up_gap`` is the confidence lead over the second-best,
    so a caller can distinguish a decisive match from a coin-flip.
    """
    # Prune: only same-tag candidates are worth the per-node scoring. If the tag
    # itself changed (rare), fall back to scoring everything.
    candidates = root.find_all(fp["tag"])
    considered = len(candidates)
    if not candidates:
        candidates = root.find_all(True)
        considered = len(candidates)

    scored = sorted(
        (_Scored(el, _score(fp, el)) for el in candidates),
        key=lambda s: s.score,
        reverse=True,
    )
    if not scored:
        return MatchResult(None, 0.0, 0.0, considered, 0)

    best = scored[0]
    runner_up = scored[1].score if len(scored) > 1 else 0.0
    gap = round(best.score - runner_up, 2)
    if best.score >= threshold:
        return MatchResult(best.el, best.score, gap, considered, len(scored))
    return MatchResult(None, best.score, gap, considered, len(scored))
