"""A plain-LLM answerer: answer from parametric knowledge, no web search.

This is the zero-cost baseline contestant — it reuses whatever ``LLMClient`` you
configure (e.g. a free OpenRouter model) and needs no search API key. It also
makes a genuinely interesting benchmark axis: does a dedicated search engine
actually beat an LLM answering from memory on obscure questions?
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from papich_bench.answerers.base import Answerer
from papich_bench.config import DEFAULT_FREE_MODEL, LLMSpec, Settings
from papich_bench.llm import build_llm
from papich_bench.llm.base import LLMClient
from papich_bench.models import AnswerContent
from papich_bench.registry import register_answerer

_DIRECT_SYSTEM = (
    "Answer the question directly and factually from your own knowledge. "
    "You have no web access. If you are not sure, say so plainly rather than "
    "inventing details."
)


class _DirectAnswer(BaseModel):
    answer: str


@register_answerer("llm_direct")
class LLMDirectAnswerer(Answerer):
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> LLMDirectAnswerer:
        spec = LLMSpec(
            backend=str(options.get("backend", "openai")),
            model=str(options.get("model", DEFAULT_FREE_MODEL)),
        )
        return cls(build_llm(spec, settings))

    async def _answer(self, prompt: str) -> AnswerContent:
        result = await self._llm.structured(
            system=_DIRECT_SYSTEM, prompt=prompt, schema=_DirectAnswer
        )
        return AnswerContent(text=result.answer, citations=[])

    async def aclose(self) -> None:
        await self._llm.aclose()
