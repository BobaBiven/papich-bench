"""Shared fixtures and fully-offline fakes.

Registering the fakes here (module import side effect) makes them available to
every test via the normal registry, exercising the real lookup path without any
network calls.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from papich_bench.answerers.base import Answerer
from papich_bench.config import Settings
from papich_bench.llm.base import LLMClient, SchemaT
from papich_bench.models import AnswerContent, Citation
from papich_bench.registry import register_answerer


@register_answerer("fake")
class FakeAnswerer(Answerer):
    """Returns a canned answer and counts how often it is actually called."""

    calls = 0

    async def _answer(self, prompt: str) -> AnswerContent:
        type(self).calls += 1
        return AnswerContent(
            text=f"Canned answer to: {prompt}",
            citations=[Citation(url="https://example.com", title="Example")],
            raw={"prompt": prompt},
        )


@register_answerer("boom")
class BoomAnswerer(Answerer):
    """Always fails, to exercise error handling."""

    async def _answer(self, prompt: str) -> AnswerContent:
        raise RuntimeError("kaboom")


class FakeLLM(LLMClient):
    """Returns a fixed payload validated against whatever schema is requested."""

    def __init__(self, payload: dict[str, Any], model: str = "fake-model") -> None:
        self.model = model
        self._payload = payload
        self.calls = 0

    async def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        self.calls += 1
        return schema.model_validate(self._payload)


class Echo(BaseModel):
    answer: str


@pytest.fixture
def judge_payload() -> dict[str, Any]:
    return {
        "found_score": 2,
        "found_reasoning": "surfaced the key fact",
        "truthful_score": 1,
        "truthful_reasoning": "mostly correct",
    }


@pytest.fixture
def fake_llm(judge_payload: dict[str, Any]) -> FakeLLM:
    return FakeLLM(judge_payload)


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture(autouse=True)
def _reset_fake_calls() -> None:
    FakeAnswerer.calls = 0
