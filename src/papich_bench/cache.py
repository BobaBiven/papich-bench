"""A small on-disk JSON cache.

Answerer responses and judgements are cached keyed by their meaningful inputs
so re-running a benchmark (or just re-rendering the report) never re-bills an
API. Delete the ``.cache/`` directory to force a fresh run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class JSONCache:
    """Namespaced key/value cache backed by one JSON file per entry."""

    def __init__(self, root: str | Path, *, enabled: bool = True) -> None:
        self.root = Path(root)
        self.enabled = enabled

    def _path(self, namespace: str, key_parts: dict[str, Any]) -> Path:
        blob = json.dumps(key_parts, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
        return self.root / namespace / f"{digest}.json"

    def get(self, namespace: str, key_parts: dict[str, Any]) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        path = self._path(namespace, key_parts)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, namespace: str, key_parts: dict[str, Any], value: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path(namespace, key_parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
