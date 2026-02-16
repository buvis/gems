from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.zettel.domain.interfaces.expression_evaluator import ExpressionEvaluator
from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository
from buvis.pybase.zettel.domain.templates import HookRunner, ZettelTemplate
from buvis.pybase.zettel.domain.value_objects.query_spec import QuerySpec
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
    _default_cache_path,
)
from buvis.pybase.zettel.infrastructure.persistence.template_loader import (
    discover_templates,
    run_template_hooks,
)
from buvis.pybase.zettel.infrastructure.query import output_formatter, query_spec_parser
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


def get_repo(*, extensions: list[str] | None = None) -> ZettelRepository:
    return MarkdownZettelRepository(extensions=extensions)


def get_formatter() -> ZettelFormatter:
    return MarkdownZettelFormatter()


def get_evaluator() -> ExpressionEvaluator:
    return python_eval


def get_templates() -> dict[str, ZettelTemplate]:
    return discover_templates(get_evaluator())


def get_hook_runner() -> HookRunner:
    return run_template_hooks


def get_cache_path() -> str:
    return _default_cache_path()


def parse_query_file(path: str) -> QuerySpec:
    return query_spec_parser.parse_query_file(path)


def parse_query_spec(raw: dict[str, Any]) -> QuerySpec:
    return query_spec_parser.parse_query_spec(raw)


def parse_query_string(yaml_str: str) -> QuerySpec:
    return query_spec_parser.parse_query_string(yaml_str)


def resolve_query_file(name_or_path: str, *, bundled_dir: Path | None = None) -> Path:
    return query_spec_parser.resolve_query_file(name_or_path, bundled_dir=bundled_dir)


def list_query_files(*, bundled_dir: Path | None = None) -> dict[str, Path]:
    return query_spec_parser.list_query_files(bundled_dir=bundled_dir)


def format_query_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return output_formatter.format_csv(rows, columns)


def format_query_html(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return output_formatter.format_html(rows, columns)


def format_query_json(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return output_formatter.format_json(rows, columns)


def format_query_jsonl(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return output_formatter.format_jsonl(rows, columns)


def format_query_kanban(
    rows: list[dict[str, Any]],
    columns: list[str],
    group_by: str,
) -> None:
    output_formatter.format_kanban(rows, columns, group_by)


def format_query_markdown(rows: list[dict[str, Any]], columns: list[str]) -> str:
    return output_formatter.format_markdown(rows, columns)


def format_query_pdf(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    return output_formatter.format_pdf(rows, columns)


def format_query_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    output_formatter.format_table(rows, columns)
