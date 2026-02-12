from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field


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


@dataclass
class QueryOutput:
    format: str = "table"  # table | csv | markdown | json | jsonl | html | pdf | tui
    file: str | None = None
    limit: int | None = None


@dataclass
class QueryExpand:
    field: str
    as_: str = "item"
    filter: str | None = None


@dataclass
class QuerySpec:
    source: QuerySource = dc_field(default_factory=QuerySource)
    filter: QueryFilter | None = None
    expand: QueryExpand | None = None
    sort: list[QuerySort] = dc_field(default_factory=list)
    columns: list[QueryColumn] = dc_field(default_factory=list)
    output: QueryOutput = dc_field(default_factory=QueryOutput)
