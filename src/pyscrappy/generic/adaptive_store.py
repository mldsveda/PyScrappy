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
