from __future__ import annotations

import re
from datetime import datetime
from functools import cached_property, cmp_to_key
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.zettel.domain.value_objects.query_spec import QueryColumn, QueryFilter

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
    from buvis.pybase.zettel.domain.interfaces.expression_evaluator import (
        ExpressionEvaluator,
    )
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelReader
    from buvis.pybase.zettel.domain.value_objects.query_spec import (
        QuerySpec,
    )

_DEFAULT_COLUMNS = ["id", "title", "date", "type", "tags", "file_path"]


class QueryZettelsUseCase:
    def __init__(self, repository: ZettelReader, evaluator: ExpressionEvaluator) -> None:
        self.repository = repository
        self.evaluator = evaluator

    def execute(self, spec: QuerySpec) -> list[dict[str, Any]]:
        directory = spec.source.directory
        if directory is None:
            msg = "source.directory is required"
            raise ValueError(msg)
        directory = str(Path(directory).expanduser().resolve())

        metadata_eq, remaining = _extract_metadata_eq(spec.filter)
        zettels = self.repository.find_all(directory, spec.source.extensions, metadata_eq=metadata_eq)

        if remaining:
            zettels = [z for z in zettels if _matches(z, remaining, self.evaluator)]

        columns = spec.columns or [QueryColumn(field=f) for f in _DEFAULT_COLUMNS]

        if spec.expand:
            rows = _expand(zettels, spec.expand, columns, self.evaluator)
            if spec.sort:
                rows = _sort_rows(rows, spec.sort)
        else:
            if spec.sort:
                zettels = _sort_zettels(zettels, spec.sort)
            rows = [_project(z, columns, self.evaluator) for z in zettels]

        if spec.output.limit:
            rows = rows[: spec.output.limit]

        return rows


def _extract_metadata_eq(
    f: QueryFilter | None,
) -> tuple[dict[str, Any] | None, QueryFilter | None]:
    """Extract simple eq conditions from a top-level 'and' filter.

    Returns (metadata_eq_dict, original_filter). The dict is passed to the
    repository as an optimization hint (can be pushed into Rust). The
    original filter is always returned unchanged for post-Zettel validation.
    """
    if f is None:
        return None, None

    if f.combinator != "and":
        return None, f

    conditions: dict[str, Any] = {}
    for child in f.children:
        if child.field and child.operator == "eq" and child.expr is None and not child.children:
            conditions[child.field.replace("-", "_")] = child.value

    if not conditions:
        return None, f

    return conditions, f


def _get_field(zettel: Zettel, name: str) -> Any:
    if hasattr(zettel, name):
        return getattr(zettel, name)
    data = zettel.get_data()
    if name in data.metadata:
        return data.metadata[name]
    if name in data.reference:
        return data.reference[name]
    if name == "file_path":
        return data.file_path
    return None


def _matches(zettel: Zettel, f: QueryFilter, evaluator: ExpressionEvaluator) -> bool:
    if f.combinator == "and":
        return all(_matches(zettel, c, evaluator) for c in f.children)
    if f.combinator == "or":
        return any(_matches(zettel, c, evaluator) for c in f.children)
    if f.combinator == "not":
        return not _matches(zettel, f.children[0], evaluator)

    if f.expr is not None:
        variables = _zettel_variables(zettel)
        return bool(evaluator(f.expr, variables))

    assert f.field is not None
    assert f.operator is not None
    field_val = _get_field(zettel, f.field.replace("-", "_"))
    if field_val is None and f.field.replace("_", "-") != f.field:
        field_val = _get_field(zettel, f.field)

    return _apply_operator(f.operator, field_val, f.value)


def _apply_operator(op: str, field_val: Any, value: Any) -> bool:
    if op == "eq":
        return bool(field_val == value)
    if op == "ne":
        return bool(field_val != value)
    if op == "gt":
        return field_val is not None and field_val > value
    if op == "ge":
        return field_val is not None and field_val >= value
    if op == "lt":
        return field_val is not None and field_val < value
    if op == "le":
        return field_val is not None and field_val <= value
    if op == "in":
        return field_val in value
    if op == "contains":
        if field_val is None:
            return False
        return value in field_val
    if op == "regex":
        if field_val is None:
            return False
        return bool(re.search(str(value), str(field_val)))
    msg = f"Unknown operator: {op}"
    raise ValueError(msg)


def _sort_zettels(zettels: list[Zettel], sort_fields: list[Any]) -> list[Zettel]:
    def compare(a: Zettel, b: Zettel) -> int:
        for sf in sort_fields:
            va = _get_field(a, sf.field)
            vb = _get_field(b, sf.field)
            # None sorts last
            if va is None and vb is None:
                continue
            if va is None:
                return 1
            if vb is None:
                return -1
            if va < vb:
                result = -1
            elif va > vb:
                result = 1
            else:
                continue
            return result if sf.order == "asc" else -result
        return 0

    return sorted(zettels, key=cmp_to_key(compare))


def _sort_rows(rows: list[dict[str, Any]], sort_fields: list[Any]) -> list[dict[str, Any]]:
    def compare(a: dict[str, Any], b: dict[str, Any]) -> int:
        for sf in sort_fields:
            va = a.get(sf.field)
            vb = b.get(sf.field)
            if va is None and vb is None:
                continue
            if va is None:
                return 1
            if vb is None:
                return -1
            if va < vb:
                result = -1
            elif va > vb:
                result = 1
            else:
                continue
            return result if sf.order == "asc" else -result
        return 0

    return sorted(rows, key=cmp_to_key(compare))


def _expand(
    zettels: list[Zettel],
    expand: Any,
    columns: list[QueryColumn],
    evaluator: ExpressionEvaluator,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for z in zettels:
        items = _get_field(z, expand.field) or []
        for item in items:
            extra = {expand.as_: item}
            if expand.filter:
                variables = {**_zettel_variables(z), **extra}
                if not evaluator(expand.filter, variables):
                    continue
            rows.append(_project(z, columns, evaluator, extra))
    return rows


def _project(
    zettel: Zettel,
    columns: list[QueryColumn],
    evaluator: ExpressionEvaluator,
    extra_variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for col in columns:
        label = col.label or col.field or col.expr or "?"
        if col.field:
            val = _get_field(zettel, col.field)
            if col.format and isinstance(val, datetime):
                val = val.strftime(col.format)
            row[label] = val
        elif col.expr:
            variables = _zettel_variables(zettel)
            if extra_variables:
                variables.update(extra_variables)
            row[label] = evaluator(col.expr, variables)
    return row


def _zettel_variables(zettel: Zettel) -> dict[str, Any]:
    data = zettel.get_data()
    variables: dict[str, Any] = {}
    variables.update(data.metadata)
    variables.update(data.reference)
    if data.file_path:
        variables["file_path"] = data.file_path
    # Expose all @property / @cached_property attributes from the zettel's actual class
    for cls in type(zettel).__mro__:
        for attr, desc in vars(cls).items():
            if isinstance(desc, (property, cached_property)) and not attr.startswith("_"):
                variables.setdefault(attr, getattr(zettel, attr, None))
    return variables
