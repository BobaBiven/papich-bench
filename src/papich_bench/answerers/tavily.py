"""Tavily search answerer — the default search contestant (has a free tier).

Tavily returns a synthesized ``answer`` plus ranked source results in one call,
which maps cleanly onto our ``AnswerContent``.
"""

from __future__ import annotations

from typing import Any

import httpx

from papich_bench.answerers.base import Answerer
from papich_bench.config import Settings
from papich_bench.models import AnswerContent, Citation
from papich_bench.registry import register_answerer

TAVILY_URL = "https://api.tavily.com/search"


@register_answerer("tavily")
class TavilyAnswerer(Answerer):
    def __init__(self, api_key: str, *, max_results: int = 5) -> None:
        self._api_key = api_key
        self._max_results = max_results
        self._client = httpx.AsyncClient(timeout=30.0)

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> TavilyAnswerer:
        api_key = settings.require("tavily_api_key", needed_by="the 'tavily' answerer")
        return cls(api_key, max_results=int(options.get("max_results", 5)))

    async def _answer(self, prompt: str) -> AnswerContent:
        response = await self._client.post(
            TAVILY_URL,
            json={
                "api_key": self._api_key,
                "query": prompt,
                "include_answer": "advanced",
                "max_results": self._max_results,
            },
        )
        response.raise_for_status()
        data = response.json()
        citations = [
            Citation(url=r["url"], title=r.get("title"))
            for r in data.get("results", [])
            if r.get("url")
        ]
        return AnswerContent(
            text=data.get("answer") or "",
            citations=citations,
            raw=data,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
