from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from buvis.pybase.configuration import get_config_dirs
from buvis.pybase.zettel.domain.templates import (
    Hook,
    ZettelTemplate,
    _discover_python_templates,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.expression_evaluator import (
        ExpressionEvaluator,
    )

logger = logging.getLogger(__name__)

# points to src/lib/buvis/pybase/zettel/domain/templates
_BUNDLED_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "domain" / "templates"


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


def _create_project_dir(data: ZettelData, zettelkasten_path: Path) -> None:
    project_dir = zettelkasten_path.parent / "projects" / str(data.metadata.get("id", "unknown"))
    project_dir.mkdir(parents=True, exist_ok=True)
    data.metadata["resources"] = f"[project resources]({project_dir.as_uri()})"


def run_template_hooks(
    hooks: list[Hook],
    data: ZettelData,
    zettelkasten_path: Path,
) -> None:
    registry = {"create_project_dir": _create_project_dir}
    for hook in hooks:
        handler = registry.get(hook.name)
        if handler is None:
            logger.warning("No hook handler registered for '%s'", hook.name)
            continue
        handler(data, zettelkasten_path)


__all__ = ["discover_templates", "discover_yaml_templates", "run_template_hooks"]
