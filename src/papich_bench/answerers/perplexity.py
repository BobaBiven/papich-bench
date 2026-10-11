"""Perplexity Sonar answerer.

Sonar is an OpenAI-style chat endpoint that answers with live web grounding and
returns citations alongside the message.
"""

from __future__ import annotations

from typing import Any

import httpx

from papich_bench.answerers.base import Answerer
from papich_bench.config import Settings
from papich_bench.models import AnswerContent, Citation
from papich_bench.registry import register_answerer

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


@register_answerer("perplexity")
class PerplexityAnswerer(Answerer):
    def __init__(self, api_key: str, *, model: str = "sonar") -> None:
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=60.0)

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> PerplexityAnswerer:
        api_key = settings.require("perplexity_api_key", needed_by="the 'perplexity' answerer")
        return cls(api_key, model=str(options.get("model", "sonar")))

    async def _answer(self, prompt: str) -> AnswerContent:
        response = await self._client.post(
            PERPLEXITY_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        citations: list[Citation] = []
        for result in data.get("search_results", []):
            if result.get("url"):
                citations.append(Citation(url=result["url"], title=result.get("title")))
        if not citations:
            citations = [Citation(url=url) for url in data.get("citations", [])]
        return AnswerContent(text=text, citations=citations, raw=data)

    async def aclose(self) -> None:
        await self._client.aclose()
