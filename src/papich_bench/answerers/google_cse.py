"""Google via the Programmable Search / Custom Search JSON API + a summarizer.

The Custom Search JSON API gives 100 queries/day at no cost, but Google has
closed it to new customers and shuts it down on 2027-01-01 — new users should use
``google_serpapi`` instead. Existing customers need an API key and a
Programmable Search Engine id (see .env.example).
"""

from __future__ import annotations

from typing import Any

import httpx

from papich_bench.answerers._search_base import SearchResult, SummarizingSearchAnswerer
from papich_bench.config import Settings
from papich_bench.llm.base import LLMClient
from papich_bench.registry import register_answerer

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


@register_answerer("google_cse")
class GoogleCSEAnswerer(SummarizingSearchAnswerer):
    def __init__(
        self, api_key: str, cse_id: str, summarizer: LLMClient, *, num_results: int = 5
    ) -> None:
        super().__init__(summarizer)
        self._api_key = api_key
        self._cse_id = cse_id
        self._num_results = min(num_results, 10)
        self._client = httpx.AsyncClient(timeout=30.0)

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> GoogleCSEAnswerer:
        api_key = settings.require("google_api_key", needed_by="the 'google_cse' answerer")
        cse_id = settings.require("google_cse_id", needed_by="the 'google_cse' answerer")
        return cls(
            api_key,
            cse_id,
            cls._build_summarizer(settings, options),
            num_results=int(options.get("num_results", 5)),
        )

    async def _search(self, prompt: str) -> list[SearchResult]:
        response = await self._client.get(
            GOOGLE_CSE_URL,
            params={
                "key": self._api_key,
                "cx": self._cse_id,
                "q": prompt,
                "num": self._num_results,
            },
        )
        response.raise_for_status()
        items = response.json().get("items", [])[: self._num_results]
        return [
            SearchResult(url=r["link"], title=r.get("title"), snippet=r.get("snippet", ""))
            for r in items
            if r.get("link")
        ]

    async def aclose(self) -> None:
        await self._client.aclose()
        await super().aclose()
