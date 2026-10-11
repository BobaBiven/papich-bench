"""The ``Answerer`` interface every benchmark contestant implements.

Subclasses implement ``_answer(prompt)`` and return an ``AnswerContent``. The
base class ``run(prompt, step_id)`` wraps that with timing and error capture, so
one misbehaving engine records an error instead of sinking the whole run.

Conversation context (for branching flows) is handled *outside* the answerer:
the runner folds prior turns into the prompt string via ``contextualize`` before
calling ``run``, so every answerer type — search engine or LLM — sees follow-ups
uniformly without needing its own chat state.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, ClassVar

from pydantic import BaseModel

from papich_bench.config import Settings
from papich_bench.models import Answer, AnswerContent


class Turn(BaseModel):
    """One prior question/answer pair, for conversation context."""

    question: str
    answer: str


def contextualize(prompt: str, history: Sequence[Turn]) -> str:
    """Fold prior turns into a single prompt string for the current question."""
    if not history:
        return prompt
    lines = ["Earlier in this conversation:"]
    for turn in history:
        lines.append(f"Q: {turn.question}")
        lines.append(f"A: {turn.answer}")
    lines.append("")
    lines.append(f"Now answer this follow-up question:\n{prompt}")
    return "\n".join(lines)


class Answerer(ABC):
    """A single benchmark contestant: takes a question, returns an answer.

    ``name`` is set by the ``@register_answerer`` decorator.
    """

    name: ClassVar[str]

    @classmethod
    def from_settings(cls, settings: Settings, options: dict[str, Any]) -> Answerer:
        """Build an instance from global settings + per-answerer options.

        The default ignores both; override when an answerer needs a key or a
        configurable model.
        """
        return cls()

    @abstractmethod
    async def _answer(self, prompt: str) -> AnswerContent:
        """Produce an answer for ``prompt``. May raise; ``run`` handles it."""

    async def run(self, prompt: str, step_id: str) -> Answer:
        """Time the call, capture failures, and return a populated ``Answer``."""
        start = time.perf_counter()
        try:
            content = await self._answer(prompt)
            return Answer(
                answerer=self.name,
                step_id=step_id,
                text=content.text,
                citations=content.citations,
                latency_s=round(time.perf_counter() - start, 3),
                raw=content.raw,
            )
        except Exception as exc:
            return Answer(
                answerer=self.name,
                step_id=step_id,
                latency_s=round(time.perf_counter() - start, 3),
                error=f"{type(exc).__name__}: {exc}",
            )

    async def aclose(self) -> None:
        """Release resources (HTTP clients). Override if needed."""
        return None
