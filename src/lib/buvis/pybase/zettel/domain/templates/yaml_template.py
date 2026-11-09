from __future__ import annotations

from collections import defaultdict
from typing import Any

from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel.domain.interfaces.expression_evaluator import ExpressionEvaluator
from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class YamlTemplate:
    """Template loaded from a YAML dict.

    Besides ``name``, ``extends``, ``questions``, ``metadata`` and ``sections``
    the YAML may set the optional placement attributes documented on
    ``ZettelTemplate`` (``folder``, ``file_stem``, ``default_tags``,
    ``body_section``) and a ``reference`` mapping for the backmatter. ``{slug}``
    is available wherever ``{title}`` is.
    """

    def __init__(
        self,
        raw: dict[str, Any],
        base: Any | None,
        evaluator: ExpressionEvaluator,
    ) -> None:
        self.name: str = raw["name"]
        self.folder: str = raw.get("folder", getattr(base, "folder", ""))
        self.file_stem: str = raw.get("file_stem", getattr(base, "file_stem", "id"))
        if self.file_stem not in ("id", "slug"):
            raise ValueError(f"template '{self.name}': file_stem must be 'id' or 'slug', not {self.file_stem!r}")
        self.default_tags: list[str] = list(raw.get("default_tags", getattr(base, "default_tags", [])))
        self.body_section: str | None = raw.get("body_section", getattr(base, "body_section", None))
        self._raw = raw
        self._base = base
        self._evaluator = evaluator

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
        answers = {**answers, "slug": StringOperator.slugify(str(answers.get("title", "")))}
        if self._base:
            data: ZettelData = self._base.build_data(answers)
        else:
            data = ZettelData()
            data.metadata["title"] = answers.get("title", "")

        for key, val in self._raw.get("metadata", {}).items():
            data.metadata[key] = _resolve_value(val, answers, self._evaluator)

        yaml_sections = self._raw.get("sections")
        if yaml_sections is not None:
            data.sections = [
                (
                    _resolve_str(s["heading"], answers),
                    _resolve_str(s.get("body", ""), answers),
                )
                for s in yaml_sections
            ]

        for key, val in self._raw.get("reference", {}).items():
            data.reference[key] = _resolve_value(val, answers, self._evaluator)

        return data

    def hooks(self) -> list[Hook]:
        return self._base.hooks() if self._base else []


def _resolve_value(
    val: Any,
    answers: dict[str, Any],
    evaluator: ExpressionEvaluator,
) -> Any:
    if isinstance(val, dict) and "eval" in val:
        return evaluator(val["eval"], answers)
    if isinstance(val, str):
        return _resolve_str(val, answers)
    return val


def _resolve_str(template: str, answers: dict[str, Any]) -> str:
    return template.format_map(defaultdict(str, answers))
