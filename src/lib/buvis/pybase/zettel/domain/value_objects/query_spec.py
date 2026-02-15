from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from buvis.pybase.zettel.domain.value_objects.property_schema import PropertyDef


@dataclass
class QuerySource:
    directory: str | None = None
    recursive: bool = True
    extensions: list[str] = dc_field(default_factory=lambda: ["md"])


@dataclass
class QueryFilter:
    operator: str | None = None  # eq, ne, gt, ge, lt, le, in, contains, regex
    field: str | None = None
    value: object = None
    combinator: str | None = None  # and, or, not
    children: list[QueryFilter] = dc_field(default_factory=list)
    expr: str | None = None  # arbitrary python expression (returns bool)


@dataclass
class QuerySort:
    field: str
    order: str = "asc"  # asc | desc


@dataclass
class QueryColumn:
    field: str | None = None
    expr: str | None = None
    label: str | None = None
    format: str | None = None
    widget: str | None = None  # text | date | checkbox | select | link
    editable: bool = False
    options: list[str] = dc_field(default_factory=list)


@dataclass
class QueryOutput:
    format: str = "table"  # table | csv | markdown | json | jsonl | html | pdf | tui | kanban
    file: str | None = None
    limit: int | None = None
    sample: int | None = None
    group_by: str | None = None


@dataclass
class QueryExpand:
    field: str
    as_: str = "item"
    filter: str | None = None


@dataclass
class QueryLookup:
    name: str
    source: QuerySource = dc_field(default_factory=QuerySource)
    filter: QueryFilter | None = None
    match: str | None = None


@dataclass
class DashboardConfig:
    title: str | None = None
    auto_refresh: bool = True


# --- Item view ---


@dataclass
class ItemField:
    field: str
    editable: bool = False
    widget: str | None = None


@dataclass
class ItemSection:
    heading: str
    fields: list[ItemField] | None = None  # property group
    section: str | None = None  # zettel body section heading
    editable: bool = False
    display: str = "auto"  # auto | markdown


@dataclass
class ItemViewSpec:
    title: str = "{title}"
    subtitle: str | None = None
    sections: list[ItemSection] = dc_field(default_factory=list)


# --- Actions ---


@dataclass
class ActionSpec:
    name: str
    label: str
    scope: str = "item"  # item | list | both
    handler: str = "patch"
    args: dict[str, Any] = dc_field(default_factory=dict)
    confirm: str | None = None  # confirmation message template, None = no confirm


@dataclass
class QuerySpec:
    source: QuerySource = dc_field(default_factory=QuerySource)
    filter: QueryFilter | None = None
    expand: QueryExpand | None = None
    sort: list[QuerySort] = dc_field(default_factory=list)
    columns: list[QueryColumn] = dc_field(default_factory=list)
    output: QueryOutput = dc_field(default_factory=QueryOutput)
    dashboard: DashboardConfig | None = None
    schema: dict[str, PropertyDef] = dc_field(default_factory=dict)
    item: ItemViewSpec | None = None
    lookups: list[QueryLookup] = dc_field(default_factory=list)
    actions: list[ActionSpec] = dc_field(default_factory=list)
