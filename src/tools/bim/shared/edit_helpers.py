from __future__ import annotations

from typing import Any

_EDIT_FIELD_MAP = {"title": "title", "zettel_type": "type", "processed": "processed", "publish": "publish"}


def build_edit_changes(kwargs: dict[str, Any], extra_sets: tuple[str, ...]) -> dict[str, Any]:
    """Extract edit changes from kwargs and --set flags."""
    changes: dict[str, Any] = {}
    for kwarg_key, change_key in _EDIT_FIELD_MAP.items():
        value = kwargs.get(kwarg_key)
        if value is not None:
            changes[change_key] = value
    tags = kwargs.get("tags")
    if tags is not None:
        changes["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    for s in extra_sets:
        if "=" in s:
            k, v = s.split("=", 1)
            changes[k] = v
    return changes
