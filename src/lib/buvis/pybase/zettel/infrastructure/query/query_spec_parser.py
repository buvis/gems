from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from buvis.pybase.configuration import get_config_dirs
from buvis.pybase.zettel.domain.value_objects.property_schema import PropertyDef
from buvis.pybase.zettel.domain.value_objects.query_spec import (
    ActionSpec,
    DashboardConfig,
    ItemField,
    ItemSection,
    ItemViewSpec,
    QueryColumn,
    QueryExpand,
    QueryFilter,
    QueryOutput,
    QuerySort,
    QuerySource,
    QuerySpec,
)


def parse_query_spec(raw: dict[str, Any]) -> QuerySpec:
    source = _parse_source(raw.get("source", {}))
    filt = _parse_filter(raw.get("filter")) if "filter" in raw else None
    expand = _parse_expand(raw["expand"]) if "expand" in raw else None
    sort = _parse_sort(raw.get("sort", []))
    columns = _parse_columns(raw.get("columns", []))
    output = _parse_output(raw.get("output", {}))
    dashboard = _parse_dashboard(raw["dashboard"]) if "dashboard" in raw else None
    schema = _parse_schema(raw["schema"]) if "schema" in raw else {}
    item = _parse_item(raw["item"]) if "item" in raw else None
    actions = _parse_actions(raw.get("actions", []))

    # Auto-inject hidden file_path column when any column is editable
    if columns and any(c.editable for c in columns):
        if not any(c.field == "file_path" for c in columns):
            columns.append(QueryColumn(field="file_path"))

    return QuerySpec(
        source=source, filter=filt, expand=expand, sort=sort,
        columns=columns, output=output, dashboard=dashboard,
        schema=schema, item=item, actions=actions,
    )


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


def _parse_expand(raw: dict[str, Any]) -> QueryExpand:
    if not isinstance(raw, dict) or "field" not in raw:
        msg = f"Expand must be a mapping with 'field' key, got {raw}"
        raise ValueError(msg)
    return QueryExpand(
        field=raw["field"],
        as_=raw.get("as", "item"),
        filter=raw.get("filter"),
    )


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
            widget=item.get("widget"),
            editable=bool(item.get("editable", False)),
            options=item.get("options", []),
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
        sample=raw.get("sample"),
    )


def _parse_dashboard(raw: dict[str, Any]) -> DashboardConfig:
    return DashboardConfig(
        title=raw.get("title"),
        auto_refresh=raw.get("auto_refresh", True),
    )


def _parse_schema(raw: dict[str, Any]) -> dict[str, PropertyDef]:
    result: dict[str, PropertyDef] = {}
    for name, defn in raw.items():
        if isinstance(defn, dict):
            result[name] = PropertyDef(
                type=defn.get("type", "text"),
                label=defn.get("label"),
                options=defn.get("options", []),
            )
    return result


def _parse_item(raw: dict[str, Any]) -> ItemViewSpec:
    sections: list[ItemSection] = []
    for sec_raw in raw.get("sections", []):
        fields = None
        if "fields" in sec_raw:
            fields = [
                ItemField(
                    field=f["field"],
                    editable=bool(f.get("editable", False)),
                    widget=f.get("widget"),
                )
                for f in sec_raw["fields"]
            ]
        sections.append(
            ItemSection(
                heading=sec_raw["heading"],
                fields=fields,
                section=sec_raw.get("section"),
                editable=bool(sec_raw.get("editable", False)),
                display=sec_raw.get("display", "auto"),
            )
        )
    return ItemViewSpec(
        title=raw.get("title", "{title}"),
        subtitle=raw.get("subtitle"),
        sections=sections,
    )


def _parse_actions(raw: list[dict[str, Any]]) -> list[ActionSpec]:
    result: list[ActionSpec] = []
    for act in raw:
        if not isinstance(act, dict) or "name" not in act or "label" not in act:
            msg = f"Action must have 'name' and 'label', got {act}"
            raise ValueError(msg)
        result.append(
            ActionSpec(
                name=act["name"],
                label=act["label"],
                scope=act.get("scope", "item"),
                handler=act.get("handler", "patch"),
                args=act.get("args", {}),
                confirm=act.get("confirm"),
            )
        )
    return result


def resolve_query_file(name_or_path: str, bundled_dir: Path | None = None) -> Path:
    """Resolve a query name or path to an actual file.

    If the value contains '/' or ends with .yaml/.yml, treat as path.
    Otherwise search config dirs' queries/ subdirs (highest priority first),
    then fall back to bundled_dir.
    """
    if "/" in name_or_path or name_or_path.endswith((".yaml", ".yml")):
        return Path(name_or_path)

    searched: list[Path] = []
    for config_dir in get_config_dirs():
        candidate = config_dir / "queries" / f"{name_or_path}.yaml"
        searched.append(candidate)
        if candidate.is_file():
            return candidate

    if bundled_dir is not None:
        candidate = bundled_dir / f"{name_or_path}.yaml"
        searched.append(candidate)
        if candidate.is_file():
            return candidate

    msg = f"Query '{name_or_path}' not found. Searched:\n" + "\n".join(
        f"  {p}" for p in searched
    )
    raise FileNotFoundError(msg)


def list_query_files(bundled_dir: Path | None = None) -> dict[str, Path]:
    """Discover available query files. Returns {stem: path}.

    Bundled dir has lowest priority; config dirs override by name.
    """
    found: dict[str, Path] = {}
    if bundled_dir is not None and bundled_dir.is_dir():
        for f in sorted(bundled_dir.glob("*.yaml")):
            found[f.stem] = f
    for config_dir in reversed(get_config_dirs()):
        queries_dir = config_dir / "queries"
        if not queries_dir.is_dir():
            continue
        for f in sorted(queries_dir.glob("*.yaml")):
            found[f.stem] = f
    return found
