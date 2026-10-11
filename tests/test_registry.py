"""Registry behaviour and that the built-in answerers are discoverable."""

from __future__ import annotations

import pytest

from papich_bench import answerers as _answerers  # noqa: F401
from papich_bench.answerers.base import Answerer
from papich_bench.registry import available_answerers, get_answerer, register_answerer


def test_builtins_registered() -> None:
    names = available_answerers()
    for expected in (
        "tavily",
        "perplexity",
        "google_serpapi",
        "google_cse",
        "duckduckgo",
        "llm_websearch",
        "llm_direct",
    ):
        assert expected in names


def test_get_unknown_raises() -> None:
    with pytest.raises(KeyError, match="unknown answerer"):
        get_answerer("does-not-exist")


def test_name_is_set_by_decorator() -> None:
    assert get_answerer("tavily").name == "tavily"


def test_duplicate_registration_raises() -> None:
    with pytest.raises(ValueError, match="already registered"):

        @register_answerer("tavily")
        class _Dup(Answerer):
            async def _answer(self, prompt: str): ...
