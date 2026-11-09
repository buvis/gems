from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
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


HookRunner = Callable[[list[Hook], ZettelData, Path], "list[str] | None"]
"""Runs a template's hooks against the prepared data; returns warnings, if any."""


class ZettelTemplate(Protocol):
    """A note template.

    Templates may also expose these optional attributes; readers use
    ``getattr(template, name, default)`` so a template without them keeps working:

    - ``folder`` (``str``, default ``""``): subdirectory of the zettelkasten the
      note is written to.
    - ``file_stem`` (``"id"`` or ``"slug"``, default ``"id"``): name the file
      after the id or after the slugified title. A slug path that exists fails
      at once instead of waiting for the next id.
    - ``default_tags`` (``list[str]``, default ``[]``): tags every note of this
      template carries; another template's note cannot use them.
    - ``body_section`` (``str | None``, default ``None``): heading of the
      section a supplied body is appended to; the first section otherwise.
    """

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
    "HookRunner",
    "Question",
    "ZettelTemplate",
]
