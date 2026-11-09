from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from buvis.pybase.configuration import get_config_dirs
from buvis.pybase.formatting import StringOperator
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
        try:
            found[raw["name"]] = YamlTemplate(raw, base=base, evaluator=evaluator)
        except ValueError as exc:
            logger.warning("Skipping template %s: %s", yaml_file, exc)


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


HookHandler = Callable[[ZettelData, Path, "Path | None"], "str | None"]
"""A hook mutates the prepared data; a returned string is a warning for the user."""


def _create_project_dir(data: ZettelData, _zettelkasten_path: Path, path_projects: Path | None) -> str | None:
    """Link ``<path_projects>/<id>-<slug>`` as the resources folder and create it when the root exists."""
    if path_projects is None:
        return "project resources folder skipped: path_projects is not set"
    slug = StringOperator.slugify(str(data.metadata.get("title", "")))
    name = "-".join(part for part in (str(data.metadata.get("id", "unknown")), slug) if part)
    root = path_projects.expanduser().absolute()
    project_dir = root / name
    data.metadata["resources"] = f"[project resources]({project_dir.as_uri()})"
    if not root.is_dir():
        return f"project resources folder {project_dir} not created: {root} does not exist"
    project_dir.mkdir(exist_ok=True)
    return None


def _set_parent_reference(data: ZettelData, zettelkasten_path: Path, _path_projects: Path | None) -> str | None:
    note_id, title = data.metadata.get("id", ""), data.metadata.get("title", "")
    data.reference["parent"] = f"[[{zettelkasten_path.name}/{note_id}|{title}]]"
    return None


def _set_illustration_link(data: ZettelData, _zettelkasten_path: Path, _path_projects: Path | None) -> str | None:
    if data.sections:
        heading, body = data.sections[0]
        data.sections[0] = (heading, body.replace("{id}", str(data.metadata.get("id", ""))))
    return None


_HOOK_REGISTRY: dict[str, HookHandler] = {
    "create_project_dir": _create_project_dir,
    "set_parent_reference": _set_parent_reference,
    "set_illustration_link": _set_illustration_link,
}


def run_template_hooks(
    hooks: list[Hook],
    data: ZettelData,
    zettelkasten_path: Path,
    *,
    path_projects: Path | None = None,
) -> list[str]:
    """Run ``hooks`` against ``data`` before it is saved; return the warnings they raised."""
    warnings: list[str] = []
    for hook in hooks:
        handler = _HOOK_REGISTRY.get(hook.name)
        if handler is None:
            logger.warning("No hook handler registered for '%s'", hook.name)
            continue
        warning = handler(data, zettelkasten_path, path_projects)
        if warning:
            warnings.append(warning)
    return warnings


__all__ = ["discover_templates", "discover_yaml_templates", "run_template_hooks"]
