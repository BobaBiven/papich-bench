"""Anthropic (Claude) backend for the ``LLMClient`` interface.

Uses the SDK's structured-output helper (``messages.parse`` with
``output_format=<pydantic model>``), which validates the response against the
schema for us.
"""

from __future__ import annotations

import anthropic

from papich_bench.config import Settings
from papich_bench.llm.base import LLMClient, SchemaT


class AnthropicLLM(LLMClient):
    """Claude, via the official Anthropic SDK."""

    def __init__(self, settings: Settings, model: str = "claude-sonnet-5") -> None:
        api_key = settings.require("anthropic_api_key", needed_by=f"Anthropic model {model!r}")
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        response = await self._client.messages.parse(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError("Anthropic returned no parsed output")
        return parsed

    async def aclose(self) -> None:
        await self._client.close()
