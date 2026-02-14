from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

logger = logging.getLogger(__name__)


@dataclass
class Question:
    key: str
    prompt: str
    default: Any = None
    choices: list[str] | None = None
    required: bool = False


@dataclass
class Hook:
    name: str
    fn: Callable[[ZettelData, Path], None] = field(repr=False)


class ZettelTemplate(Protocol):
    name: str

    def questions(self) -> list[Question]: ...

    def build_data(self, answers: dict[str, Any]) -> ZettelData: ...

    def hooks(self) -> list[Hook]: ...


def _discover_python_templates() -> dict[str, ZettelTemplate]:
    templates: dict[str, ZettelTemplate] = {}
    package = importlib.import_module(__package__)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__package__}.{info.name}")
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (
                isinstance(obj, type)
                and obj is not ZettelTemplate
                and hasattr(obj, "name")
                and hasattr(obj, "questions")
                and hasattr(obj, "build_data")
                and hasattr(obj, "hooks")
            ):
                instance = obj()
                templates[instance.name] = instance
    return templates


__all__ = [
    "Hook",
    "Question",
    "ZettelTemplate",
    "_discover_python_templates",
]
