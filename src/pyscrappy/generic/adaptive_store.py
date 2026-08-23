"""Persistence for adaptive-selector fingerprints.

A small JSON store keyed by ``identifier`` (and optionally namespaced by the site
URL, so the same identifier on two sites doesn't collide). Kept deliberately
simple — no extra dependencies — since the payload is a handful of small dicts.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def default_store_path() -> Path:
    """Where fingerprints live by default: ``$PYSCRAPPY_HOME/adaptive.json`` or
    ``~/.pyscrappy/adaptive.json``. Override per call with an explicit path."""
    base = os.environ.get("PYSCRAPPY_HOME")
    root = Path(base) if base else Path.home() / ".pyscrappy"
    return root / "adaptive.json"


def _heal_log_path(store_path: Path) -> Path:
    """The heal-log lives beside the fingerprint store as ``<name>.heal.ndjson``.

    NDJSON (one heal per line, append-only) so the audit trail accumulates every
    relocation instead of being overwritten the way a fingerprint is."""
    return store_path.with_suffix(".heal.ndjson")


class AdaptiveStore:
    """Load/save element fingerprints to a JSON file, namespaced by site."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_store_path()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _key(self, identifier: str, namespace: str | None) -> str:
        return f"{namespace}::{identifier}" if namespace else identifier

    def save(
        self, identifier: str, fingerprint: dict[str, Any], namespace: str | None = None
    ) -> None:
        data = self._load()
        data[self._key(identifier, namespace)] = fingerprint
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically: serialize to a temp file in the same directory,
        # then os.replace() it over the target. os.replace() is an atomic
        # rename on both POSIX and Windows, so a reader always sees either
        # the old complete file or the new complete file — never a partial one.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        f = None
        try:
            f = os.fdopen(fd, "w", encoding="utf-8")
            json.dump(data, f, indent=2)
            f.close()
            os.replace(tmp, self.path)
        except BaseException:
            if f is not None:
                try:
                    f.close()
                except OSError:
                    pass
            else:
                try:
                    os.close(fd)
                except OSError:
                    pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def retrieve(self, identifier: str, namespace: str | None = None) -> dict[str, Any] | None:
        return self._load().get(self._key(identifier, namespace))

    def record_heal(
        self,
        identifier: str,
        *,
        namespace: str | None,
        confidence: float,
        runner_up_gap: float,
        before: dict[str, Any] | None,
        after: dict[str, Any],
    ) -> None:
        """Append one relocation to the append-only heal log.

        A heal is a change to what a selector resolves to, so it is recorded with
        the fingerprint *before* and *after*, plus the confidence and the gap to
        the runner-up. This keeps drift observable: the log is the audit trail that
        an in-place fingerprint overwrite would otherwise erase.
        """
        from datetime import datetime, timezone

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "identifier": identifier,
            "namespace": namespace,
            "confidence": confidence,
            "runner_up_gap": runner_up_gap,
            "before": before,
            "after": after,
        }
        log_path = _heal_log_path(self.path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def heal_log(self, identifier: str | None = None, namespace: str | None = None) -> list[dict]:
        """Return recorded heals, newest last. Optionally filter by identifier
        and/or namespace. Empty list if nothing has healed yet."""
        log_path = _heal_log_path(self.path)
        if not log_path.exists():
            return []
        entries: list[dict] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if identifier is not None and entry.get("identifier") != identifier:
                continue
            if namespace is not None and entry.get("namespace") != namespace:
                continue
            entries.append(entry)
        return entries

    def heal_report(self, namespace: str | None = None) -> list[dict]:
        """Summarize recorded heals, one row per (identifier, namespace) selector.

        Turns the append-only heal log into an at-a-glance drift report: how often
        each selector has healed, its latest and lowest confidence (a low value is
        where relocation was shakiest and worth a human look), and when it last
        healed. Rows are sorted by heal count, most-healed first — the selectors
        that have drifted the most surface at the top.

        Each row: ``identifier``, ``namespace``, ``heals``, ``last_confidence``,
        ``min_confidence``, ``avg_confidence``, ``last_healed`` (timestamp).
        """
        grouped: dict[tuple[str, str | None], list[dict]] = {}
        for e in self.heal_log(namespace=namespace):
            key = (e.get("identifier", ""), e.get("namespace"))
            grouped.setdefault(key, []).append(e)

        report: list[dict] = []
        for (identifier, ns), heals in grouped.items():
            confidences = [h["confidence"] for h in heals if h.get("confidence") is not None]
            report.append(
                {
                    "identifier": identifier,
                    "namespace": ns,
                    "heals": len(heals),
                    "last_confidence": confidences[-1] if confidences else None,
                    "min_confidence": min(confidences) if confidences else None,
                    "avg_confidence": (
                        round(sum(confidences) / len(confidences), 2) if confidences else None
                    ),
                    "last_healed": heals[-1].get("timestamp"),
                }
            )
        report.sort(key=lambda r: r["heals"], reverse=True)
        return report
