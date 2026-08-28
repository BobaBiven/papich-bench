"""Load and validate the questions dataset.

The dataset is a YAML file the user authors — a list of items, each with a
question, a reference answer, and (optionally) a note on what "found what I
wanted" means. See ``datasets/obscure.yaml`` for the seed set.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from papich_bench.config import ConfigError
from papich_bench.models import Question


def load_dataset(path: str | Path) -> list[Question]:
    """Parse ``path`` into validated ``Question`` objects.

    Accepts either a top-level list or a ``{questions: [...]}`` mapping.
    """
    file = Path(path)
    if not file.exists():
        raise ConfigError(f"dataset not found: {file}")

    raw = yaml.safe_load(file.read_text(encoding="utf-8"))
    items = raw.get("questions", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list) or not items:
        raise ConfigError(f"dataset {file} is empty or malformed (expected a list of questions)")

    questions = [Question.model_validate(item) for item in items]

    seen: set[str] = set()
    for q in questions:
        if q.id in seen:
            raise ConfigError(f"duplicate question id in dataset: {q.id!r}")
        seen.add(q.id)

    return questions
