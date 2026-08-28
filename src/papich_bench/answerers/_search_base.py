"""Shared base for answerers that fetch search results and summarize them.

A plain search engine returns ranked links, not an "answer." To make such an
engine comparable to Perplexity/Tavily (which synthesize an answer), we hand its
top results to a small LLM and ask it to answer strictly from those snippets.

``SerpAPI``, ``DuckDuckGo``, and ``Google CSE`` answerers differ only in *how*
they fetch results, so that's the single abstract method subclasses implement.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pydantic import BaseModel

from papich_bench.answerers.base import Answerer
from papich_bench.config import DEFAULT_FREE_MODEL, LLMSpec, Settings
from papich_bench.llm import build_llm
from papich_bench.llm.base import LLMClient
from papich_bench.models import AnswerContent, Citation

_SUMMARIZE_SYSTEM = (
    "You are answering a question using ONLY the web search snippets provided. "
    "Give a direct, factual answer. If the snippets do not contain the answer, "
    "say so plainly rather than guessing."
)


class SearchResult(BaseModel):
    """A normalized search hit, independent of which engine produced it."""

    url: str
    title: str | None = None
    snippet: str = ""


class _TextAnswer(BaseModel):
    answer: str


def summarizer_spec(options: dict[str, Any]) -> LLMSpec:
    """The LLM spec used to summarize results, from per-answerer options."""
    return LLMSpec(
        backend=str(options.get("summarizer_backend", "openai")),
        model=str(options.get("summarizer_model", DEFAULT_FREE_MODEL)),
    )


class SummarizingSearchAnswerer(Answerer):
    """Fetch results via ``_search`` then summarize them into an answer."""

    def __init__(self, summarizer: LLMClient) -> None:
        self._summarizer = summarizer

    @classmethod
    def _build_summarizer(cls, settings: Settings, options: dict[str, Any]) -> LLMClient:
        return build_llm(summarizer_spec(options), settings)

    @abstractmethod
    async def _search(self, prompt: str) -> list[SearchResult]:
        """Return the engine's top results for ``prompt``."""

    async def _answer(self, prompt: str) -> AnswerContent:
        results = await self._search(prompt)
        citations = [Citation(url=r.url, title=r.title) for r in results]
        snippets = "\n\n".join(
            f"[{i + 1}] {r.title or ''}\n{r.snippet}\n{r.url}" for i, r in enumerate(results)
        )
        summary = await self._summarizer.structured(
            system=_SUMMARIZE_SYSTEM,
            prompt=f"Question: {prompt}\n\nSearch results:\n{snippets}",
            schema=_TextAnswer,
        )
        return AnswerContent(
            text=summary.answer,
            citations=citations,
            raw={"results": [r.model_dump() for r in results]},
        )

    async def aclose(self) -> None:
        await self._summarizer.aclose()
