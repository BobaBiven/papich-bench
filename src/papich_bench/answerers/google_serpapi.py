"""Google (via SerpAPI) + an LLM summarizer.

SerpAPI returns raw Google organic results; the shared base turns them into a
comparable answer via a small (by default free) summarizer LLM.
"""

from __future__ import annotations

from typing import Any

import httpx

from papich_bench.answerers._search_base import SearchResult, SummarizingSearchAnswerer
from papich_bench.config import Settings
from papich_bench.llm.base import LLMClient
from papich_bench.registry import register_answerer

SERPAPI_URL = "https://serpapi.com/search.json"


@register_answerer("google_serpapi")
class GoogleSerpAPIAnswerer(SummarizingSearchAnswerer):
    def __init__(self, api_key: str, summarizer: LLMClient, *, num_results: int = 5) -> None:
        super().__init__(summarizer)
        self._api_key = api_key
        self._num_results = num_results
        self._client = httpx.AsyncClient(timeout=30.0)

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> GoogleSerpAPIAnswerer:
        api_key = settings.require("serpapi_api_key", needed_by="the 'google_serpapi' answerer")
        return cls(
            api_key,
            cls._build_summarizer(settings, options),
            num_results=int(options.get("num_results", 5)),
        )

    async def _search(self, prompt: str) -> list[SearchResult]:
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
        organic = response.json().get("organic_results", [])[: self._num_results]
        return [
            SearchResult(url=r["link"], title=r.get("title"), snippet=r.get("snippet", ""))
            for r in organic
            if r.get("link")
        ]

    async def aclose(self) -> None:
        await self._client.aclose()
        await super().aclose()
