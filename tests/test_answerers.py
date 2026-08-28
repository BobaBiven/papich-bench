"""Unit tests for individual answerers that can run fully offline."""

from __future__ import annotations

from papich_bench.answerers._search_base import SearchResult
from papich_bench.answerers.duckduckgo import DuckDuckGoAnswerer
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


async def test_summarizing_search_answerer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """DuckDuckGo exercises the shared search+summarize base (no network)."""
    llm = FakeLLM({"answer": "Testville is the capital."})
    answerer = DuckDuckGoAnswerer(llm)

    async def fake_search(prompt: str) -> list[SearchResult]:
        return [SearchResult(url="https://a.example", title="A", snippet="capital is Testville")]

    monkeypatch.setattr(answerer, "_search", fake_search)
    answer = await answerer.run(_question())

    assert answer.ok
    assert answer.text == "Testville is the capital."
    assert answer.citations[0].url == "https://a.example"
    assert llm.calls == 1
