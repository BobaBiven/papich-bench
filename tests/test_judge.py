"""Judge prompt construction and verdict parsing."""

from __future__ import annotations

from papich_bench.judge import Judge, _build_prompt
from papich_bench.models import Answer, FlowStep

from .conftest import FakeLLM


def _step() -> FlowStep:
    return FlowStep(
        id="q1",
        prompt="What is the capital of Testland?",
        reference_answer="Testville",
        wanted="The name Testville.",
    )


async def test_judge_returns_scores(fake_llm: FakeLLM) -> None:
    judge = Judge(fake_llm)
    answer = Answer(answerer="fake", step_id="q1", text="It is Testville.")
    verdict = await judge.judge(_step(), answer)
    assert verdict.found_score == 2
    assert verdict.truthful_score == 1
    assert verdict.combined == 3
    assert fake_llm.calls == 1


def test_prompt_includes_reference_and_candidate() -> None:
    answer = Answer(answerer="fake", step_id="q1", text="Some candidate text")
    prompt = _build_prompt(_step(), answer)
    assert "Testville" in prompt  # reference answer
    assert "Some candidate text" in prompt  # candidate
    assert "fake" in prompt  # answerer name


def test_prompt_handles_empty_answer() -> None:
    answer = Answer(answerer="fake", step_id="q1", text="")
    prompt = _build_prompt(_step(), answer)
    assert "no answer" in prompt
