"""Dataset loading and validation (single questions and flows)."""

from __future__ import annotations

from pathlib import Path

import pytest

from papich_bench.config import ConfigError
from papich_bench.dataset import load_dataset


def test_loads_seed_dataset() -> None:
    flows = load_dataset("datasets/obscure.yaml")
    assert len(flows) >= 5
    first = flows[0]
    assert first.id
    assert len(first.steps) == 1  # single questions load as one-step flows
    assert first.steps[0].prompt
    assert first.steps[0].reference_answer


def test_loads_flow_with_branches() -> None:
    flows = {f.id: f for f in load_dataset("datasets/flows.yaml")}
    amazon = flows["amazon-flow"]
    assert [s.id for s in amazon.steps] == ["q1", "q2"]
    assert amazon.step("q1").branches[1].then == "q2"  # type: ignore[union-attr]


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
