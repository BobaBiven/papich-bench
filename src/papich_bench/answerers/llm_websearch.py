"""An LLM-with-web-search agent contestant (Claude native web search).

This makes "an LLM that searches the web" compete head-to-head with dedicated
search engines. It uses Claude's server-side ``web_search`` tool, so the model
runs the searches itself and returns a cited answer.
"""

from __future__ import annotations

from typing import Any

import anthropic

from papich_bench.answerers.base import Answerer
from papich_bench.config import Settings
from papich_bench.models import AnswerContent, Citation
from papich_bench.registry import register_answerer

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}
MAX_PAUSE_RESTARTS = 5


@register_answerer("llm_websearch")
class LLMWebSearchAnswerer(Answerer):
    def __init__(self, api_key: str, *, model: str = "claude-sonnet-5", max_uses: int = 5) -> None:
        self._model = model
        self._max_uses = max_uses
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> LLMWebSearchAnswerer:
        api_key = settings.require("anthropic_api_key", needed_by="the 'llm_websearch' answerer")
        return cls(
            api_key,
            model=str(options.get("model", "claude-sonnet-5")),
            max_uses=int(options.get("max_uses", 5)),
        )

    async def _answer(self, prompt: str) -> AnswerContent:
        """Ask Claude with web search on. When the server tool hits its per-turn
        limit (``pause_turn``), re-send the conversation so it can continue."""
        tools = [{**WEB_SEARCH_TOOL, "max_uses": self._max_uses}]
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        text_parts: list[str] = []
        citations: list[Citation] = []
        for _ in range(MAX_PAUSE_RESTARTS + 1):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                tools=tools,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )
            _collect(response.content, text_parts, citations)
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})

        return AnswerContent(
            text="\n".join(p for p in text_parts if p).strip(),
            citations=_dedupe(citations),
            raw={"model": self._model},
        )

    async def aclose(self) -> None:
        await self._client.close()


def _collect(content: Any, text_parts: list[str], citations: list[Citation]) -> None:
    """Pull answer text and cited URLs out of a response's content blocks."""
    for block in content:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_parts.append(block.text)
            for cit in getattr(block, "citations", None) or []:
                url = getattr(cit, "url", None)
                if url:
                    citations.append(Citation(url=url, title=getattr(cit, "title", None)))
        elif btype == "web_search_tool_result":
            results = getattr(block, "content", None) or []
            if isinstance(results, list):
                for r in results:
                    url = getattr(r, "url", None)
                    if url:
                        citations.append(Citation(url=url, title=getattr(r, "title", None)))


def _dedupe(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    out: list[Citation] = []
    for c in citations:
        if c.url not in seen:
            seen.add(c.url)
            out.append(c)
    return out
