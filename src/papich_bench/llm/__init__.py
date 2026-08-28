"""LLM backends and a factory that builds one from an ``LLMSpec``."""

from __future__ import annotations

from papich_bench.config import ConfigError, LLMSpec, Settings
from papich_bench.llm.anthropic_client import AnthropicLLM
from papich_bench.llm.base import LLMClient
from papich_bench.llm.openai_compatible import OpenAICompatibleLLM

__all__ = ["AnthropicLLM", "LLMClient", "OpenAICompatibleLLM", "build_llm"]


def build_llm(spec: LLMSpec, settings: Settings) -> LLMClient:
    """Construct the LLM backend named by ``spec.backend``."""
    if spec.backend == "anthropic":
        return AnthropicLLM(settings, model=spec.model)
    if spec.backend == "openai":
        return OpenAICompatibleLLM(settings, model=spec.model)
    raise ConfigError(f"unknown LLM backend {spec.backend!r} (expected 'anthropic' or 'openai')")
