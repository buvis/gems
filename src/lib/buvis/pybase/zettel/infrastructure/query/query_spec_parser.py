from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from buvis.pybase.zettel.domain.value_objects.query_spec import (
    QueryColumn,
    QueryFilter,
    QueryOutput,
    QuerySort,
    QuerySource,
    QuerySpec,
)


def parse_query_spec(raw: dict[str, Any]) -> QuerySpec:
    source = _parse_source(raw.get("source", {}))
    filt = _parse_filter(raw.get("filter")) if "filter" in raw else None
    sort = _parse_sort(raw.get("sort", []))
    columns = _parse_columns(raw.get("columns", []))
    output = _parse_output(raw.get("output", {}))
    return QuerySpec(source=source, filter=filt, sort=sort, columns=columns, output=output)


def parse_query_file(path: str) -> QuerySpec:
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        msg = f"Query file must contain a YAML mapping, got {type(raw).__name__}"
        raise ValueError(msg)
    return parse_query_spec(raw)


def parse_query_string(yaml_str: str) -> QuerySpec:
    raw = yaml.safe_load(yaml_str)
    if not isinstance(raw, dict):
        msg = f"Query string must be a YAML mapping, got {type(raw).__name__}"
        raise ValueError(msg)
    return parse_query_spec(raw)


def _parse_source(raw: dict[str, Any]) -> QuerySource:
    return QuerySource(
        directory=raw.get("directory"),
        recursive=raw.get("recursive", True),
        extensions=raw.get("extensions", ["md"]),
    )


def _parse_filter(raw: Any) -> QueryFilter:
    if not isinstance(raw, dict):
        msg = f"Filter must be a mapping, got {type(raw).__name__}"
        raise ValueError(msg)

    if "and" in raw:
        return QueryFilter(
            combinator="and",
            children=[_parse_filter(c) for c in raw["and"]],
        )
    if "or" in raw:
        return QueryFilter(
            combinator="or",
            children=[_parse_filter(c) for c in raw["or"]],
        )
    if "not" in raw:
        return QueryFilter(
            combinator="not",
            children=[_parse_filter(raw["not"])],
        )

    if "expr" in raw:
        return QueryFilter(expr=raw["expr"])

    # field condition: {field_name: {operator: value}}
    if len(raw) != 1:
        msg = f"Field condition must have exactly one key, got {list(raw.keys())}"
        raise ValueError(msg)
    field_name = next(iter(raw))
    condition = raw[field_name]
    if not isinstance(condition, dict) or len(condition) != 1:
        msg = f"Condition for '{field_name}' must be {{operator: value}}"
        raise ValueError(msg)
    op = next(iter(condition))
    valid_ops = {"eq", "ne", "gt", "ge", "lt", "le", "in", "contains", "regex"}
    if op not in valid_ops:
        msg = f"Unknown operator '{op}', valid: {sorted(valid_ops)}"
        raise ValueError(msg)
    return QueryFilter(operator=op, field=field_name, value=condition[op])


def _parse_sort(raw: list[dict[str, Any]]) -> list[QuerySort]:
    result = []
    for item in raw:
        if not isinstance(item, dict) or "field" not in item:
            msg = f"Sort item must have 'field' key, got {item}"
            raise ValueError(msg)
        result.append(QuerySort(field=item["field"], order=item.get("order", "asc")))
    return result


def _parse_columns(raw: list[dict[str, Any]]) -> list[QueryColumn]:
    result = []
    for item in raw:
        if not isinstance(item, dict):
            msg = f"Column item must be a mapping, got {type(item).__name__}"
            raise ValueError(msg)
        col = QueryColumn(
            field=item.get("field"),
            expr=item.get("expr"),
            label=item.get("label"),
            format=item.get("format"),
        )
        if not col.field and not col.expr:
            msg = "Column must have 'field' or 'expr'"
            raise ValueError(msg)
        result.append(col)
    return result


def _parse_output(raw: dict[str, Any]) -> QueryOutput:
    return QueryOutput(
        format=raw.get("format", "table"),
        file=raw.get("file"),
        limit=raw.get("limit"),
    )
