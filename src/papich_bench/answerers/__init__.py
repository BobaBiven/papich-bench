"""Answerer implementations.

Importing this package imports every concrete answerer module, which runs their
``@register_answerer`` decorators so the runner can look them up by name.
Add a new engine by dropping a module here and importing it below.
"""

from __future__ import annotations

from papich_bench.answerers import (  # noqa: F401
    duckduckgo,
    google_cse,
    google_serpapi,
    llm_direct,
    llm_websearch,
    perplexity,
    tavily,
)
from papich_bench.answerers.base import Answerer

__all__ = ["Answerer"]
