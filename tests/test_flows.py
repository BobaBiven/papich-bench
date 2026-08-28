"""Branching flow walks — the router picks the next step (fully offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from papich_bench import runner
from papich_bench.config import AnswererSpec, LLMSpec, RunConfig, Settings

from .conftest import FakeLLM

FLOW_YAML = """
questions:
  - id: amazon-flow
    steps:
      - id: q1
        prompt: First product sold on Amazon?
        reference_answer: A book by Hofstadter.
        wanted: names the book
        branches:
          - if: names the exact book title
            then: stop
          - if: says a book but not the title
            then: q2
          - if: wrong
            then: stop
      - id: q2
        prompt: Which book title exactly?
        reference_answer: Fluid Concepts and Creative Analogies
        wanted: the exact title
"""


def _config(tmp_path: Path) -> RunConfig:
    ds = tmp_path / "flows.yaml"
    ds.write_text(FLOW_YAML, encoding="utf-8")
    return RunConfig(
        dataset=str(ds),
        answerers=[AnswererSpec(name="fake")],
        judge=LLMSpec(backend="anthropic", model="fake"),
        cache_dir=str(tmp_path / "cache"),
        output_dir=str(tmp_path / "out"),
    )


def _llm(judge_payload: dict, branch_index: int) -> FakeLLM:
    return FakeLLM(
        judge_payload,
        by_schema={
            "Judgement": judge_payload,
            "RouterDecision": {"branch_index": branch_index, "reason": "test"},
        },
    )


async def test_flow_branches_into_followup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, judge_payload: dict
) -> None:
    monkeypatch.setattr(runner, "build_llm", lambda spec, settings: _llm(judge_payload, 1))
    report = await runner.run_benchmark(_config(tmp_path), Settings(), use_cache=False)

    run = report.results[0].runs[0]
    assert [s.step_id for s in run.steps] == ["q1", "q2"]  # branch 1 -> q2
    assert run.steps[0].next == "q2"


async def test_flow_stops_on_first_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, judge_payload: dict
) -> None:
    monkeypatch.setattr(runner, "build_llm", lambda spec, settings: _llm(judge_payload, 0))
    report = await runner.run_benchmark(_config(tmp_path), Settings(), use_cache=False)

    run = report.results[0].runs[0]
    assert [s.step_id for s in run.steps] == ["q1"]  # branch 0 -> stop
    assert run.steps[0].next == "stop"
