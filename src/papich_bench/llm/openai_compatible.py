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

import asyncio
import json
from typing import Any

import httpx

from papich_bench.config import Settings
from papich_bench.llm.base import LLMClient, SchemaT

_MAX_RETRIES = 4
_MAX_BACKOFF_S = 30.0


class OpenAICompatibleLLM(LLMClient):
    """Any OpenAI-compatible chat-completions endpoint.

    Without ``OPENAI_API_KEY`` it sends a dummy key, which local Ollama accepts.
    """

    def __init__(self, settings: Settings, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self._base_url = settings.openai_base_url.rstrip("/")
        self._api_key = settings.openai_api_key or "not-needed"
        self._client = httpx.AsyncClient(timeout=90.0)

    async def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_system = (
            f"{system}\n\n"
            "Respond with a single JSON object and nothing else. It must validate "
            f"against this JSON schema:\n{schema_json}"
        )
        messages = [
            {"role": "system", "content": full_system},
            {"role": "user", "content": prompt},
        ]
        content = await self._chat(messages)
        return schema.model_validate_json(_strip_code_fence(content))

    async def _chat(self, messages: list[dict[str, str]]) -> str:
        """Try JSON mode first, then a plain request for models that reject
        ``response_format`` — the schema is in the prompt and validated either way."""
        base: dict[str, Any] = {"model": self.model, "temperature": 0, "messages": messages}
        attempts: tuple[dict[str, Any], ...] = ({"response_format": {"type": "json_object"}}, {})
        for extra in attempts:
            response = await self._post_with_backoff({**base, **extra})
            if extra and response.status_code in (400, 404, 422):
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise RuntimeError("OpenAI-compatible endpoint returned non-text content")
            return content
        raise RuntimeError("unreachable")

    async def _post_with_backoff(self, payload: dict[str, Any]) -> httpx.Response:
        """POST once, retrying on 429/5xx with exponential backoff + Retry-After."""
        delay = 2.0
        response = None
        for attempt in range(_MAX_RETRIES + 1):
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            if response.status_code != 429 and response.status_code < 500:
                return response
            if attempt == _MAX_RETRIES:
                break
            retry_after = _retry_after_seconds(response) or delay
            await asyncio.sleep(min(retry_after, _MAX_BACKOFF_S))
            delay *= 2
        assert response is not None
        return response

    async def aclose(self) -> None:
        await self._client.aclose()


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse a numeric Retry-After header (seconds), if present."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _strip_code_fence(text: str) -> str:
    """Some models wrap JSON in ```json fences; peel them off if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()
