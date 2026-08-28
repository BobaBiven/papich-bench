"""Dataset loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from papich_bench.config import ConfigError
from papich_bench.dataset import load_dataset


def test_loads_seed_dataset() -> None:
    questions = load_dataset("datasets/obscure.yaml")
    assert len(questions) >= 5
    first = questions[0]
    assert first.id
    assert first.prompt
    assert first.reference_answer


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_dataset(tmp_path / "nope.yaml")


def test_empty_dataset_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("questions: []\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_dataset(path)


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dupe.yaml"
    path.write_text(
        "questions:\n"
        "  - id: a\n    prompt: q1\n    reference_answer: r1\n"
        "  - id: a\n    prompt: q2\n    reference_answer: r2\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_dataset(path)


def test_accepts_bare_list(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text(
        "- id: a\n  prompt: q1\n  reference_answer: r1\n",
        encoding="utf-8",
    )
    questions = load_dataset(path)
    assert questions[0].id == "a"
