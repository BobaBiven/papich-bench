"""End-to-end runner test — fully offline via the registered fakes.

Exercises dataset -> answer -> judge -> report with no network by pointing the
judge at a ``FakeLLM`` and running the ``fake``/``boom`` answerers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from papich_bench import runner
from papich_bench.config import AnswererSpec, LLMSpec, RunConfig, Settings
from papich_bench.models import RunReport
from papich_bench.report import to_html, to_markdown

from .conftest import FakeAnswerer, FakeLLM


def _write_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "ds.yaml"
    path.write_text(
        "questions:\n"
        "  - id: q1\n    prompt: first question\n    reference_answer: ref one\n"
        "  - id: q2\n    prompt: second question\n    reference_answer: ref two\n",
        encoding="utf-8",
    )
    return path


def _config(tmp_path: Path, names: list[str]) -> RunConfig:
    return RunConfig(
        dataset=str(_write_dataset(tmp_path)),
        answerers=[AnswererSpec(name=n) for n in names],
        judge=LLMSpec(backend="anthropic", model="fake-model"),
        cache_dir=str(tmp_path / "cache"),
        output_dir=str(tmp_path / "out"),
        concurrency=2,
    )


@pytest.fixture(autouse=True)
def _patch_judge_llm(monkeypatch: pytest.MonkeyPatch, judge_payload: dict) -> None:
    monkeypatch.setattr(runner, "build_llm", lambda spec, settings: FakeLLM(judge_payload))


async def test_run_produces_scored_report(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ["fake"])
    report = await runner.run_benchmark(cfg, Settings(), use_cache=False)

    assert isinstance(report, RunReport)
    assert len(report.results) == 2
    board = report.leaderboard()
    assert len(board) == 1
    row = board[0]
    assert row.answerer == "fake"
    assert row.n == 2
    assert row.mean_found == 2.0
    assert row.mean_truthful == 1.0
    assert row.score_pct == 75.0  # (2+1)/4


async def test_failing_answerer_is_recorded_not_fatal(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ["fake", "boom"])
    report = await runner.run_benchmark(cfg, Settings(), use_cache=False)

    rows = {r.answerer: r for r in report.leaderboard()}
    assert rows["boom"].n_errors == 2
    assert rows["boom"].n == 0  # nothing was judged
    assert rows["fake"].n == 2  # the good answerer still ran


async def test_cache_prevents_recompute(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ["fake"])
    await runner.run_benchmark(cfg, Settings(), use_cache=True)
    assert FakeAnswerer.calls == 2  # one per question

    # Second run with the same cache should not call the answerer again.
    await runner.run_benchmark(cfg, Settings(), use_cache=True)
    assert FakeAnswerer.calls == 2


async def test_report_renders(tmp_path: Path) -> None:
    cfg = _config(tmp_path, ["fake"])
    report = await runner.run_benchmark(cfg, Settings(), use_cache=False)

    md = to_markdown(report)
    assert "Leaderboard" in md
    assert "fake" in md
    assert "first question" in md

    html = to_html(report)
    assert "<table>" in html
    assert "papich_bench results" in html

    # Round-trips through JSON like the CLI's `report` command.
    restored = RunReport.model_validate_json(report.model_dump_json())
    assert restored.leaderboard()[0].answerer == "fake"
