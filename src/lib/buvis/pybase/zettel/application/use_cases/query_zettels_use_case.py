from __future__ import annotations

import random
import re
import warnings
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
        QueryLookup,
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
        zettels = self.repository.find_all(directory, metadata_eq=metadata_eq)

        pools = (
            _resolve_lookup_pools(spec.lookups, self.repository, self.evaluator)
            if spec.lookups
            else {}
        )

        # Filter + compute lookup context per zettel
        pairs: list[tuple[Zettel, dict[str, list[Zettel]]]] = []
        for z in zettels:
            lctx = (
                _compute_lookup_context(z, spec.lookups, pools, self.evaluator)
                if pools
                else {}
            )
            if remaining and not _matches(z, remaining, self.evaluator, lctx):
                continue
            pairs.append((z, lctx))

        columns = spec.columns or [QueryColumn(field=f) for f in _DEFAULT_COLUMNS]

        if spec.expand:
            rows = _expand(pairs, spec.expand, columns, self.evaluator)
            if spec.sort:
                rows = _sort_rows(rows, spec.sort)
        else:
            if spec.sort:
                # Sort bare zettels, then re-pair via id() map
                ctx_map = {id(z): lctx for z, lctx in pairs}
                sorted_z = _sort_zettels([z for z, _ in pairs], spec.sort)
                pairs = [(z, ctx_map[id(z)]) for z in sorted_z]
            rows = [
                _project(z, columns, self.evaluator, lctx) for z, lctx in pairs
            ]

        if spec.output.limit:
            rows = rows[: spec.output.limit]

        if spec.output.sample and len(rows) > spec.output.sample:
            rows = random.sample(rows, spec.output.sample)

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


def _matches(
    zettel: Zettel,
    f: QueryFilter,
    evaluator: ExpressionEvaluator,
    lookup_context: dict[str, Any] | None = None,
) -> bool:
    if f.combinator == "and":
        return all(_matches(zettel, c, evaluator, lookup_context) for c in f.children)
    if f.combinator == "or":
        return any(_matches(zettel, c, evaluator, lookup_context) for c in f.children)
    if f.combinator == "not":
        return not _matches(zettel, f.children[0], evaluator, lookup_context)

    if f.expr is not None:
        variables = _zettel_variables(zettel)
        if lookup_context:
            variables.update(lookup_context)
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
    pairs: list[tuple[Zettel, dict[str, Any]]],
    expand: Any,
    columns: list[QueryColumn],
    evaluator: ExpressionEvaluator,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for z, lctx in pairs:
        items = _get_field(z, expand.field) or []
        for item in items:
            extra = {**lctx, expand.as_: item}
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


def _resolve_lookup_pools(
    lookups: list[QueryLookup],
    repository: ZettelReader,
    evaluator: ExpressionEvaluator,
) -> dict[str, list[Zettel]]:
    pools: dict[str, list[Zettel]] = {}
    for lookup in lookups:
        if lookup.source.directory is None:
            msg = f"Lookup '{lookup.name}' requires source.directory"
            raise ValueError(msg)
        directory = str(Path(lookup.source.directory).expanduser().resolve())
        metadata_eq, remaining = _extract_metadata_eq(lookup.filter)
        candidates = repository.find_all(directory, metadata_eq=metadata_eq)
        if remaining:
            candidates = [z for z in candidates if _matches(z, remaining, evaluator)]
        pools[lookup.name] = candidates
    return pools


def _compute_lookup_context(
    zettel: Zettel,
    lookups: list[QueryLookup],
    pools: dict[str, list[Zettel]],
    evaluator: ExpressionEvaluator,
) -> dict[str, list[Zettel]]:
    ctx: dict[str, list[Zettel]] = {}
    primary_vars = _zettel_variables(zettel)
    for lookup in lookups:
        candidates = pools.get(lookup.name, [])
        if lookup.match is None:
            warnings.warn(
                f"Lookup '{lookup.name}' has no match expression; cross-joining all candidates",
                stacklevel=2,
            )
            ctx[lookup.name] = candidates
        else:
            matched: list[Zettel] = []
            for candidate in candidates:
                variables = {**primary_vars, lookup.name: candidate}
                if evaluator(lookup.match, variables):
                    matched.append(candidate)
            ctx[lookup.name] = matched
    return ctx
