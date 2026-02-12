from __future__ import annotations

from collections import defaultdict
from typing import Any

from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


class YamlTemplate:
    """Template loaded from a YAML dict."""

    def __init__(self, raw: dict[str, Any], base: Any | None = None) -> None:
        self.name: str = raw["name"]
        self._raw = raw
        self._base = base

    def questions(self) -> list[Question]:
        base_qs = self._base.questions() if self._base else []
        yaml_qs = [
            Question(
                key=q["key"],
                prompt=q["prompt"],
                default=q.get("default"),
                choices=q.get("choices"),
                required=q.get("required", False),
            )
            for q in self._raw.get("questions", [])
        ]
        return base_qs + yaml_qs

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        if self._base:
            data: ZettelData = self._base.build_data(answers)
        else:
            data = ZettelData()
            data.metadata["title"] = answers.get("title", "")

        for key, val in self._raw.get("metadata", {}).items():
            data.metadata[key] = _resolve_value(val, answers)

        yaml_sections = self._raw.get("sections")
        if yaml_sections is not None:
            data.sections = [
                (
                    _resolve_str(s["heading"], answers),
                    _resolve_str(s.get("body", ""), answers),
                )
                for s in yaml_sections
            ]

        return data

    def hooks(self) -> list[Hook]:
        return self._base.hooks() if self._base else []


def _resolve_value(val: Any, answers: dict[str, Any]) -> Any:
    if isinstance(val, dict) and "eval" in val:
        return python_eval(val["eval"], answers)
    if isinstance(val, str):
        return _resolve_str(val, answers)
    return val


def _resolve_str(template: str, answers: dict[str, Any]) -> str:
    return template.format_map(defaultdict(str, answers))
