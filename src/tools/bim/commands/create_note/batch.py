from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import yaml
from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.create_zettel_use_case import CreateZettelUseCase
from buvis.pybase.zettel.domain.templates import ZettelTemplate

from bim.dependencies import get_hook_runner, get_repo


def create_single(
    path_zettelkasten: Path,
    template: ZettelTemplate,
    title: str,
    tags: str | None = None,
    extra_answers: dict[str, str] | None = None,
    *,
    quiet: bool = False,
) -> Path | None:
    """Create one zettel. Returns path on success, None on failure."""
    answers: dict[str, Any] = {"title": title}
    if tags:
        answers["tags"] = tags
    for q in template.questions():
        if extra_answers and q.key in extra_answers:
            answers[q.key] = extra_answers[q.key]
        elif q.default is not None:
            answers[q.key] = q.default
        elif q.required:
            console.failure(f"Missing required answer: {q.key}")
            return None
    use_case = CreateZettelUseCase(
        path_zettelkasten,
        get_repo(),
        hook_runner=get_hook_runner(),
    )
    try:
        path = use_case.execute(template, answers)
    except FileExistsError as e:
        console.failure(str(e))
        return None
    if not quiet:
        console.success(f"Created {path}")
    return path


_CSV_RESERVED = {"title", "type", "tags"}


def parse_batch_file(path: Path) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    """Parse batch spec file. Returns (default_type, default_tags, items).

    Raises ValueError on parse errors.
    """
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return _parse_yaml(path)
    if suffix == ".csv":
        return _parse_csv(path)
    raise ValueError(f"Unsupported batch file format: {suffix}")


def _parse_yaml(path: Path) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or "items" not in data:
        raise ValueError("YAML batch file must contain an 'items' key")
    default_type = data.get("type")
    default_tags = data.get("tags")
    items = []
    for item in data["items"]:
        if not isinstance(item, dict) or "title" not in item:
            raise ValueError("Each item must be a dict with a 'title' key")
        items.append({
            "title": item["title"],
            "type": item.get("type"),
            "tags": item.get("tags"),
            "answers": item.get("answers", {}),
        })
    return default_type, default_tags, items


def _parse_csv(path: Path) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    text = path.read_text()
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "title" not in reader.fieldnames:
        raise ValueError("CSV batch file must have a 'title' column")
    items = []
    for row in reader:
        answers = {k: v for k, v in row.items() if k not in _CSV_RESERVED and v}
        items.append({
            "title": row["title"],
            "type": row.get("type") or None,
            "tags": row.get("tags") or None,
            "answers": answers,
        })
    return None, None, items
