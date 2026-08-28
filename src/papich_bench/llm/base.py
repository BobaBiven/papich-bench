"""The ``LLMClient`` interface used by the judge and by LLM-based answerers.

Deliberately tiny: one method to get a validated structured object back. Any
provider that can return JSON conforming to a schema can implement it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMClient(ABC):
    """A backend that turns a prompt into a validated pydantic object."""

    model: str

    @abstractmethod
    async def structured(self, *, system: str, prompt: str, schema: type[SchemaT]) -> SchemaT:
        """Return an instance of ``schema`` produced by the model."""

    async def aclose(self) -> None:
        """Release any resources (HTTP clients). Override if needed."""
        return None
