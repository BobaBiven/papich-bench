"""A tiny name -> class registry so adding an answerer is one decorator.

    @register_answerer("tavily")
    class TavilyAnswerer(Answerer): ...

The runner never imports concrete answerers directly; it looks them up by the
name used in the YAML config. ``answerers/__init__.py`` imports every concrete
module so the decorators run on import.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from papich_bench.answerers.base import Answerer

AnswererT = TypeVar("AnswererT", bound="Answerer")

_ANSWERERS: dict[str, type[Answerer]] = {}


def register_answerer(name: str) -> Callable[[type[AnswererT]], type[AnswererT]]:
    """Class decorator that registers an ``Answerer`` subclass under ``name``."""

    def decorator(cls: type[AnswererT]) -> type[AnswererT]:
        if name in _ANSWERERS:
            raise ValueError(f"answerer {name!r} is already registered")
        cls.name = name
        _ANSWERERS[name] = cls
        return cls

    return decorator


def get_answerer(name: str) -> type[Answerer]:
    try:
        return _ANSWERERS[name]
    except KeyError:
        known = ", ".join(sorted(_ANSWERERS)) or "(none)"
        raise KeyError(f"unknown answerer {name!r}. Registered: {known}") from None


def available_answerers() -> list[str]:
    return sorted(_ANSWERERS)
