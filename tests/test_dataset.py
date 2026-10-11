"""Dataset loading and validation (single questions and flows)."""

from __future__ import annotations

from pathlib import Path

import pytest

from papich_bench.config import ConfigError
from papich_bench.dataset import load_dataset


def test_loads_default_dataset() -> None:
    flows = load_dataset("datasets/papich.yaml")
    assert len(flows) == 1
    flow = flows[0]
    assert flow.id == "papich-bench"
    assert [s.id for s in flow.steps] == ["who-is-arthas", "notable-facts", "old-dota-moments"]
    assert flow.steps[0].reference_answer


def test_loads_flow_with_branches() -> None:
    flow = load_dataset("datasets/papich.yaml")[0]
    assert flow.step("who-is-arthas").branches[0].then == "notable-facts"
    assert flow.step("notable-facts").branches[1].then == "stop"


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


def test_branch_to_unknown_step_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        "questions:\n"
        "  - id: f\n    steps:\n"
        "      - id: q1\n        prompt: p\n        reference_answer: r\n"
        "        branches:\n          - if: whatever\n            then: nowhere\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="unknown step"):
        load_dataset(path)


def test_accepts_bare_list(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- id: a\n  prompt: q1\n  reference_answer: r1\n", encoding="utf-8")
    flows = load_dataset(path)
    assert flows[0].id == "a"
