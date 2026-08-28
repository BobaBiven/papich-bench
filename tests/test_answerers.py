"""Unit tests for individual answerers that can run fully offline."""

from __future__ import annotations

from papich_bench.answerers.llm_direct import LLMDirectAnswerer
from papich_bench.models import Question

from .conftest import FakeLLM


def _question() -> Question:
    return Question(id="q", prompt="capital of Testland?", reference_answer="Testville")


async def test_llm_direct_answers_via_llm() -> None:
    llm = FakeLLM({"answer": "It is Testville."})
    answerer = LLMDirectAnswerer(llm)

    answer = await answerer.run(_question())

    assert answer.ok
    assert answer.text == "It is Testville."
    assert answer.citations == []  # no search -> no citations
    assert llm.calls == 1


async def test_llm_direct_reports_llm_failure() -> None:
    class Boom(FakeLLM):
        async def structured(self, *, system: str, prompt: str, schema: type):  # type: ignore[override,no-untyped-def]
            raise RuntimeError("model down")

    answerer = LLMDirectAnswerer(Boom({}))
    answer = await answerer.run(_question())

    assert not answer.ok
    assert "model down" in (answer.error or "")
