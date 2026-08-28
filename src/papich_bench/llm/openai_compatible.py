"""OpenAI-compatible backend for the ``LLMClient`` interface.

One adapter covers OpenAI, Groq, Google's OpenAI-compat endpoint, and local
Ollama — they all speak ``POST /chat/completions``. Only the ``base_url`` (and
key) differ, both read from ``Settings``.

Uses JSON-object mode plus the schema embedded in the prompt, then validates
with pydantic. That is the most portable path across these providers (strict
``json_schema`` response formats are not uniformly supported, especially by
Ollama and some free tiers).
"""

from __future__ import annotations

import json

import httpx

from papich_bench.config import Settings
from papich_bench.llm.base import LLMClient, SchemaT


class OpenAICompatibleLLM(LLMClient):
    """Any OpenAI-compatible chat-completions endpoint."""

    def __init__(self, settings: Settings, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self._base_url = settings.openai_base_url.rstrip("/")
        # Local Ollama needs no key; hosted providers do. Default to a dummy so
        # Ollama works out of the box, but keep any real key the user supplied.
        self._api_key = settings.openai_api_key or "not-needed"
        self._client = httpx.AsyncClient(timeout=60.0)

    async def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_system = (
            f"{system}\n\n"
            "Respond with a single JSON object and nothing else. It must validate "
            f"against this JSON schema:\n{schema_json}"
        )
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": full_system},
                {"role": "user", "content": prompt},
            ],
        }
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return schema.model_validate_json(_strip_code_fence(content))

    async def aclose(self) -> None:
        await self._client.aclose()


def _strip_code_fence(text: str) -> str:
    """Some models wrap JSON in ```json fences; peel them off if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()
