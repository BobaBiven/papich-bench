"""Google (via SerpAPI) + an LLM summarizer.

SerpAPI returns raw Google organic results; a plain search engine has no
"answer". To make it comparable to Perplexity/Tavily, we hand the top results
to a small LLM and ask it to answer the question strictly from those snippets.
The summarizer LLM is configurable (defaults to Claude Sonnet).
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel

from papich_bench.answerers.base import Answerer
from papich_bench.config import LLMSpec, Settings
from papich_bench.llm import build_llm
from papich_bench.llm.base import LLMClient
from papich_bench.models import AnswerContent, Citation
from papich_bench.registry import register_answerer

SERPAPI_URL = "https://serpapi.com/search.json"

_SUMMARIZE_SYSTEM = (
    "You are answering a question using ONLY the Google search snippets provided. "
    "Give a direct, factual answer. If the snippets do not contain the answer, say "
    "so plainly rather than guessing."
)


class _TextAnswer(BaseModel):
    answer: str


@register_answerer("google_serpapi")
class GoogleSerpAPIAnswerer(Answerer):
    def __init__(
        self,
        api_key: str,
        summarizer: LLMClient,
        *,
        num_results: int = 5,
    ) -> None:
        self._api_key = api_key
        self._summarizer = summarizer
        self._num_results = num_results
        self._client = httpx.AsyncClient(timeout=30.0)

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> GoogleSerpAPIAnswerer:
        api_key = settings.require("serpapi_api_key", needed_by="the 'google_serpapi' answerer")
        spec = LLMSpec(
            backend=str(options.get("summarizer_backend", "anthropic")),
            model=str(options.get("summarizer_model", "claude-sonnet-5")),
        )
        return cls(
            api_key,
            build_llm(spec, settings),
            num_results=int(options.get("num_results", 5)),
        )

    async def _answer(self, prompt: str) -> AnswerContent:
        response = await self._client.get(
            SERPAPI_URL,
            params={
                "engine": "google",
                "q": prompt,
                "api_key": self._api_key,
                "num": self._num_results,
            },
        )
        response.raise_for_status()
        data = response.json()
        organic = data.get("organic_results", [])[: self._num_results]

        citations = [
            Citation(url=r["link"], title=r.get("title")) for r in organic if r.get("link")
        ]
        snippets = "\n\n".join(
            f"[{i + 1}] {r.get('title', '')}\n{r.get('snippet', '')}\n{r.get('link', '')}"
            for i, r in enumerate(organic)
        )
        summary = await self._summarizer.structured(
            system=_SUMMARIZE_SYSTEM,
            prompt=f"Question: {prompt}\n\nSearch results:\n{snippets}",
            schema=_TextAnswer,
        )
        return AnswerContent(text=summary.answer, citations=citations, raw=data)

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._summarizer.aclose()
