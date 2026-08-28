"""DuckDuckGo search + an LLM summarizer.

The only fully **key-free** search contestant: DuckDuckGo needs no API key, so
paired with a free summarizer model this runs at zero cost with nothing but an
OpenRouter signup. Uses the ``ddgs`` package (an unofficial DuckDuckGo client).
"""

from __future__ import annotations

import asyncio
from typing import Any

from papich_bench.answerers._search_base import SearchResult, SummarizingSearchAnswerer
from papich_bench.config import Settings
from papich_bench.llm.base import LLMClient
from papich_bench.registry import register_answerer


@register_answerer("duckduckgo")
class DuckDuckGoAnswerer(SummarizingSearchAnswerer):
    def __init__(self, summarizer: LLMClient, *, max_results: int = 5) -> None:
        super().__init__(summarizer)
        self._max_results = max_results

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> DuckDuckGoAnswerer:
        # No search key needed — only a summarizer LLM.
        return cls(
            cls._build_summarizer(settings, options),
            max_results=int(options.get("max_results", 5)),
        )

    async def _search(self, prompt: str) -> list[SearchResult]:
        # ddgs is synchronous and does blocking I/O; run it off the event loop.
        rows = await asyncio.to_thread(self._search_sync, prompt)
        return [
            SearchResult(url=r["href"], title=r.get("title"), snippet=r.get("body", ""))
            for r in rows
            if r.get("href")
        ]

    def _search_sync(self, prompt: str) -> list[dict[str, Any]]:
        try:
            from ddgs import DDGS
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise RuntimeError(
                "the 'duckduckgo' answerer needs the 'ddgs' package (pip install ddgs)"
            ) from exc
        with DDGS() as ddgs:
            return list(ddgs.text(prompt, max_results=self._max_results))
