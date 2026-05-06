from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.zettel.infrastructure.query import output_formatter, query_spec_parser

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.expression_evaluator import ExpressionEvaluator
    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository
    from buvis.pybase.zettel.domain.templates import HookRunner, ZettelTemplate
    from buvis.pybase.zettel.domain.value_objects.query_spec import QuerySpec

    from bim.commands.doc.shared.classifier import Classifier
    from bim.commands.doc.shared.extractor import Extractor
    from bim.commands.doc.shared.issuers import IssuerRegistry
    from bim.commands.doc.shared.ocr import OCRRunner
    from bim.commands.doc.shared.pipeline import Pipeline
    from bim.commands.doc.shared.settings_models import DocSettings
    from bim.commands.doc.shared.state_db import StateDB
    from bim.commands.doc.shared.zettel_writer import ZettelWriter


def get_repo(*, extensions: list[str] | None = None) -> ZettelRepository:
    from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
        MarkdownZettelRepository,
    )

    return MarkdownZettelRepository(extensions=extensions)


def get_formatter() -> ZettelFormatter:
    from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
        MarkdownZettelFormatter,
    )

    return MarkdownZettelFormatter()


def get_evaluator() -> ExpressionEvaluator:
    from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval

    return python_eval


def get_templates() -> dict[str, ZettelTemplate]:
    from buvis.pybase.zettel.infrastructure.persistence.template_loader import discover_templates

    return discover_templates(get_evaluator())


def get_hook_runner() -> HookRunner:
    from buvis.pybase.zettel.infrastructure.persistence.template_loader import run_template_hooks

    return run_template_hooks


def get_cache_path() -> str:
    from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
        _default_cache_path,
    )

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


# --------- doc subsystem factories ---------
#
# These factories wire the bim doc subsystem. Imports are deferred to keep the
# module loadable without the optional [doc] extra installed; bim show / bim
# query continue to work without ocrmypdf, requests, or pdfminer present.


def get_state_db(settings: DocSettings) -> StateDB:
    from bim.commands.doc.shared.state_db import StateDB as _StateDB

    state_dir = settings.paths.state_dir
    if state_dir is None:
        raise ValueError("DocSettings.paths.state_dir is not set")
    return _StateDB.open(state_dir / "state.db")


def get_issuer_registry(settings: DocSettings) -> tuple[IssuerRegistry, Path, Path]:
    """Load the issuer registry and return ``(registry, registry_path, lock_path)``."""
    from bim.commands.doc.shared.issuers import load_registry

    issuers_file = settings.paths.issuers_file
    state_dir = settings.paths.state_dir
    if issuers_file is None or state_dir is None:
        raise ValueError("DocSettings.paths.{issuers_file,state_dir} is not set")
    registry = load_registry(issuers_file)
    lock_path = state_dir / "issuers.lock"
    return registry, issuers_file, lock_path


def get_ocr_runner(settings: DocSettings) -> OCRRunner:
    from bim.commands.doc.shared.ocr import OCRRunner as _OCRRunner

    state_dir = settings.paths.state_dir
    if state_dir is None:
        raise ValueError("DocSettings.paths.state_dir is not set")
    return _OCRRunner(settings=settings, state_dir=state_dir)


def get_classifier(settings: DocSettings) -> Classifier:
    from bim.commands.doc.shared.classifier import Classifier as _Classifier

    return _Classifier(settings.classifier)


def get_extractor(settings: DocSettings) -> Extractor:
    from bim.commands.doc.shared.extractor import Extractor as _Extractor

    return _Extractor(settings.classifier)


def get_zettel_writer(settings: DocSettings, repo: ZettelRepository) -> ZettelWriter:
    from bim.commands.doc.shared.zettel_writer import ZettelWriter as _ZettelWriter

    return _ZettelWriter(
        repo=repo,
        vault_root=settings.paths.vault_root,
        vault_documents_subdir=settings.paths.vault_documents_subdir,
    )


def get_health_checker() -> Callable[[DocSettings], None]:
    from bim.commands.doc.shared.health import check_health

    return check_health


def get_pipeline(settings: DocSettings, repo: ZettelRepository) -> Pipeline:
    """Wire all doc subsystem services and return a ready-to-run Pipeline."""
    from bim.commands.doc.shared.pipeline import Pipeline as _Pipeline
    from bim.commands.doc.shared.pipeline import PipelineServices

    registry, _registry_path, _lock_path = get_issuer_registry(settings)
    services = PipelineServices(
        state_db=get_state_db(settings),
        ocr_runner=get_ocr_runner(settings),
        classifier=get_classifier(settings),
        extractor=get_extractor(settings),
        registry=registry,
        zettel_writer=get_zettel_writer(settings, repo),
    )
    return _Pipeline(settings, services)
