"""Configuration: secrets from the environment, run settings from YAML.

Two layers, kept separate on purpose:

* ``Settings`` — secrets (API keys, endpoints) read from the environment / ``.env``.
* ``RunConfig`` — what to run (dataset, answerers, judge), read from a YAML file.

The CLI loads both and hands them to the runner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# A free OpenRouter model, used as the default wherever an LLM is needed at
# zero cost (the judge, `llm_direct`, and search summarizers). Free ids come and
# go — browse current ones at https://openrouter.ai/models?max_price=0.
DEFAULT_FREE_MODEL = "z-ai/glm-5.2:free"


class Settings(BaseSettings):
    """Secrets and endpoints, resolved from environment variables / ``.env``."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    tavily_api_key: str | None = None
    perplexity_api_key: str | None = None
    serpapi_api_key: str | None = None

    # Google Programmable Search (Custom Search JSON API) — free, 100 queries/day.
    google_api_key: str | None = None
    google_cse_id: str | None = None

    def require(self, attr: str, *, needed_by: str) -> str:
        """Return a secret or raise a clear, actionable error if it's unset."""
        value: str | None = getattr(self, attr, None)
        if not value:
            env_name = attr.upper()
            raise ConfigError(
                f"{needed_by} needs {env_name}, but it is not set. "
                f"Add it to your .env (see .env.example)."
            )
        return value


class LLMSpec(BaseModel):
    """Which LLM backs a role (the judge, or an LLM-based answerer)."""

    backend: str = "anthropic"  # "anthropic" | "openai"
    model: str = "claude-sonnet-5"


class AnswererSpec(BaseModel):
    """One answerer to run, plus any per-answerer overrides (e.g. model)."""

    name: str
    options: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    """Everything that defines a run, loaded from a YAML config file."""

    dataset: str = "datasets/papich.yaml"
    answerers: list[AnswererSpec] = Field(default_factory=list)
    judge: LLMSpec = Field(default_factory=LLMSpec)
    concurrency: int = 4
    carry_context: bool = True  # in flows, follow-ups see prior turns
    cache_dir: str = ".cache"
    output_dir: str = "results"

    @classmethod
    def from_yaml(cls, path: str | Path) -> RunConfig:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        # Allow the shorthand `answerers: [tavily, perplexity]` alongside the
        # full `{name: ..., options: {...}}` form.
        answerers = raw.get("answerers", [])
        raw["answerers"] = [{"name": a} if isinstance(a, str) else a for a in answerers]
        return cls.model_validate(raw)


class ConfigError(RuntimeError):
    """Raised for missing keys or malformed configuration — always user-facing."""
