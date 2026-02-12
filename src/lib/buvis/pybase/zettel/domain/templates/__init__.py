from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import yaml
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.expression_evaluator import (
        ExpressionEvaluator,
    )

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


_BUNDLED_TEMPLATE_DIR = Path(__file__).parent


def _scan_yaml_dir(
    directory: Path,
    base_templates: dict[str, ZettelTemplate],
    found: dict[str, ZettelTemplate],
    evaluator: ExpressionEvaluator,
) -> None:
    from buvis.pybase.zettel.domain.templates.yaml_template import YamlTemplate

    if not directory.is_dir():
        return
    for yaml_file in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            logger.warning("Failed to load template %s", yaml_file)
            continue
        if not isinstance(raw, dict) or "name" not in raw:
            continue
        base = None
        if extends := raw.get("extends"):
            base = base_templates.get(extends) or found.get(extends)
        found[raw["name"]] = YamlTemplate(raw, base=base, evaluator=evaluator)


def discover_yaml_templates(
    base_templates: dict[str, ZettelTemplate],
    evaluator: ExpressionEvaluator,
) -> dict[str, ZettelTemplate]:
    from buvis.pybase.configuration import get_config_dirs

    found: dict[str, ZettelTemplate] = {}
    # Bundled templates (lowest priority)
    _scan_yaml_dir(_BUNDLED_TEMPLATE_DIR, base_templates, found, evaluator)
    # Config dirs in reverse priority order so higher-priority overrides
    for config_dir in reversed(get_config_dirs()):
        _scan_yaml_dir(config_dir / "templates", base_templates, found, evaluator)
    return found


def discover_templates(evaluator: ExpressionEvaluator) -> dict[str, ZettelTemplate]:
    templates = _discover_python_templates()
    templates.update(discover_yaml_templates(templates, evaluator=evaluator))
    return templates


__all__ = [
    "Hook",
    "Question",
    "ZettelTemplate",
    "discover_templates",
    "discover_yaml_templates",
]
