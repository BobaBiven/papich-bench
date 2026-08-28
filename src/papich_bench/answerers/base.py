"""The ``Answerer`` interface every benchmark contestant implements.

Subclasses implement ``_answer(prompt)`` and return an ``AnswerContent``. The
base class ``run(question)`` wraps that with timing and error capture, so one
misbehaving engine records an error instead of sinking the whole run.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from papich_bench.config import Settings
from papich_bench.models import Answer, AnswerContent, Question


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

    async def run(self, question: Question) -> Answer:
        """Time the call, capture failures, and return a populated ``Answer``."""
        start = time.perf_counter()
        try:
            content = await self._answer(question.prompt)
            return Answer(
                answerer=self.name,
                question_id=question.id,
                text=content.text,
                citations=content.citations,
                latency_s=round(time.perf_counter() - start, 3),
                raw=content.raw,
            )
        except Exception as exc:
            return Answer(
                answerer=self.name,
                question_id=question.id,
                latency_s=round(time.perf_counter() - start, 3),
                error=f"{type(exc).__name__}: {exc}",
            )

    async def aclose(self) -> None:
        """Release resources (HTTP clients). Override if needed."""
        return None
