"""Load and validate the benchmark dataset.

The dataset is a YAML file the user authors — a list of items. Each item is
either:

* a **single question** (``id``, ``prompt``, ``reference_answer``, ``wanted``),
  which loads as a one-step flow, or
* a **flow** (``id`` + ``steps``), where each step may declare ``branches`` for
  conditional follow-ups.

See ``datasets/obscure.yaml`` (single questions) and ``datasets/flows.yaml``
(branching) for examples.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from papich_bench.config import ConfigError
from papich_bench.models import Flow, FlowStep


def load_dataset(path: str | Path) -> list[Flow]:
    """Parse ``path`` into validated ``Flow`` objects."""
    file = Path(path)
    if not file.exists():
        raise ConfigError(f"dataset not found: {file}")

    raw = yaml.safe_load(file.read_text(encoding="utf-8"))
    items = raw.get("questions", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not items:
        raise ConfigError(f"dataset {file} is empty or malformed (expected a list of items)")

    try:
        flows = [_to_flow(item) for item in items]
    except (ValueError, TypeError, KeyError) as exc:
        raise ConfigError(f"invalid dataset {file}: {exc}") from exc

    seen: set[str] = set()
    for flow in flows:
        if flow.id in seen:
            raise ConfigError(f"duplicate item id in dataset: {flow.id!r}")
        seen.add(flow.id)

    return flows


def _to_flow(item: dict[str, Any]) -> Flow:
    """Accept both the single-question shorthand and the full flow shape."""
    if "steps" in item:
        return Flow.model_validate(item)
    # Single question -> a one-step flow whose step id equals the item id.
    step = FlowStep.model_validate(
        {k: v for k, v in item.items() if k in {"id", "prompt", "reference_answer", "wanted"}}
    )
    return Flow(id=item["id"], steps=[step], tags=item.get("tags", []))
