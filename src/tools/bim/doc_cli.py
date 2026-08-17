from __future__ import annotations

import sys
from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import get_settings
from buvis.pybase.result import CommandResult

from bim.doc_rules_cli import register_rules_subcommands
from bim.settings import BimSettings

__all__ = ["register_doc_group"]


def register_doc_group(cli: click.Group) -> None:
    cli.add_command(doc)


@click.group("doc", help="Document ingestion + triage workflow")
@click.pass_context
def doc(ctx: click.Context) -> None:
    """Document subsystem - ingest, triage, and promote PDFs."""


@doc.command("ingest", help="Ingest a PDF through the OCR + classify + extract pipeline")
@click.argument(
    "pdf_path",
    type=click.Path(file_okay=True, dir_okay=False, resolve_path=True, path_type=Path),
)
@click.option("--issuer", "issuer", default=None, help="Pre-pin the issuer slug (used with issuer-inbox source)")
@click.option(
    "--source",
    "source",
    type=click.Choice(["email", "scan", "download", "issuer-inbox", "backfill-canonical", "backfill-noncanonical"]),
    default="download",
    show_default=True,
    help="Where the document entered the system",
)
@click.option(
    "--strict",
    "strict",
    is_flag=True,
    default=False,
    help="Exit non-zero on pipeline failure (for scripting). Default exits 0 on failure.",
)
@click.pass_context
def doc_ingest(
    ctx: click.Context,
    pdf_path: Path,
    issuer: str | None,
    source: str,
    strict: bool,
) -> None:
    if not pdf_path.is_file():
        console.panic(f"file not found: {pdf_path}")
        return

    settings = get_settings(ctx, BimSettings)
    if settings.doc is None:
        console.panic("[doc] section missing in bim config; configure paths.business_root etc. first")
        return

    try:
        from bim.commands.doc.ingest.ingest import CommandIngest
        from bim.commands.doc.shared.health import MissingDependency
        from bim.commands.doc.shared.progress import NoOpProgressReporter, SpinnerProgressReporter
        from bim.dependencies import get_health_checker, get_pipeline, get_repo
        from bim.params.doc_ingest import IngestParams
    except ImportError:
        console.require_import("doc")
        return

    try:
        get_health_checker()(settings.doc)
    except MissingDependency as exc:
        console.panic(str(exc))
        return

    params = IngestParams(
        source=source,
        staging_path=pdf_path,
        issuer_slug_hint=issuer,
    )
    pipeline = get_pipeline(settings.doc, get_repo())
    cmd = CommandIngest(params=params, pipeline=pipeline)
    # Show a Rich spinner with per-stage labels in interactive runs; stay
    # silent when stdout is piped/redirected so batch consumers see only the
    # final result line.
    reporter = SpinnerProgressReporter(console) if sys.stdout.isatty() else NoOpProgressReporter()
    with reporter:
        result = cmd.execute(reporter=reporter)
    _report_doc_result(result, default_failure="ingest failed", strict=strict)


@doc.command("promote", help="Promote an approved triage proposal into a filed document")
@click.argument(
    "yml_path",
    type=click.Path(file_okay=True, dir_okay=False, resolve_path=True, path_type=Path),
)
@click.option(
    "--strict",
    "strict",
    is_flag=True,
    default=False,
    help="Exit non-zero on promote failure (for scripting). Default exits 0 on failure.",
)
@click.pass_context
def doc_promote(ctx: click.Context, yml_path: Path, strict: bool) -> None:
    if not yml_path.is_file():
        console.panic(f"file not found: {yml_path}")
        return

    settings = get_settings(ctx, BimSettings)
    if settings.doc is None:
        console.panic("[doc] section missing in bim config; configure paths.business_root etc. first")
        return

    try:
        from bim.commands.doc.promote.promote import CommandPromote, PromoteServices
        from bim.commands.doc.shared.health import MissingDependency
        from bim.dependencies import (
            get_health_checker,
            get_issuer_registry,
            get_ocr_runner,
            get_repo,
            get_state_db,
            get_zettel_writer,
        )
        from bim.params.doc_promote import PromoteParams
    except ImportError:
        console.require_import("doc")
        return

    try:
        get_health_checker()(settings.doc)
    except MissingDependency as exc:
        console.panic(str(exc))
        return

    bundle = get_issuer_registry(settings.doc)
    services = PromoteServices(
        registry=bundle.registry,
        registry_path=bundle.registry_path,
        lock_path=bundle.lock_path,
        state_db=get_state_db(settings.doc),
        ocr_runner=get_ocr_runner(settings.doc),
        zettel_writer=get_zettel_writer(settings.doc, get_repo()),
    )
    cmd = CommandPromote(
        params=PromoteParams(proposed_yml_path=yml_path),
        settings=settings.doc,
        services=services,
    )
    result = cmd.execute()
    _report_doc_result(result, default_failure="promote failed", strict=strict)


@doc.command("audit", help="Read-only audit of the Business folder")
@click.pass_context
def doc_audit(ctx: click.Context) -> None:
    settings = get_settings(ctx, BimSettings)
    if settings.doc is None:
        console.panic("[doc] section missing in bim config; configure paths.business_root etc. first")
        return

    try:
        from bim.commands.doc.audit.audit import CommandAudit
        from bim.commands.doc.audit.reporter import render_stdout
        from bim.commands.doc.shared.health import MissingDependency
        from bim.dependencies import get_audit_services, get_health_checker
    except ImportError:
        console.require_import("doc")
        return

    try:
        get_health_checker()(settings.doc)
    except MissingDependency as exc:
        console.panic(str(exc))
        return

    services = get_audit_services(settings.doc)
    cmd = CommandAudit(services=services)
    result = cmd.execute()

    if not result.success:
        console.failure(result.error or "audit failed")
        return

    for w in result.warnings:
        console.warning(w)

    report = result.metadata["report"]
    render_stdout(report, console)
    console.success(f"Report: {result.metadata['report_path']}")


register_rules_subcommands(doc)


def _report_doc_result(result: CommandResult, *, default_failure: str, strict: bool = False) -> None:
    """Map a doc-subsystem ``CommandResult`` to console output.

    The ``strict`` flag is opt-in: when True, pipeline failures
    (``success=False``) panic (exit 1) instead of failing softly
    (exit 0). Triaged/duplicate outcomes (``success=True``) are NOT
    treated as failures and remain unaffected by ``strict``.
    """
    for w in result.warnings:
        console.warning(w)
    if not result.success:
        if strict:
            console.panic(result.error or default_failure)
        else:
            console.failure(result.error or default_failure)
        return
    metadata = result.metadata
    outcome = metadata.get("outcome")
    if outcome == "filed":
        pdf_path = metadata.get("pdf_path")
        zettel_path = metadata.get("zettel_path")
        if pdf_path and zettel_path:
            console.success(f"filed: {pdf_path} (zettel: {zettel_path})")
        else:
            console.success(result.output or "filed")
    elif outcome == "triaged":
        proposal_path = metadata.get("proposal_path")
        console.warning(f"triaged: review {proposal_path}" if proposal_path else "triaged")
    elif outcome == "duplicate":
        existing = metadata.get("existing_canonical_filename")
        console.warning(f"duplicate of {existing}" if existing else "duplicate")
    else:
        # promote success: no outcome key, but pdf/zettel are present.
        pdf_path = metadata.get("pdf_path")
        zettel_path = metadata.get("zettel_path")
        if pdf_path and zettel_path:
            console.success(f"promoted: {pdf_path} (zettel: {zettel_path})")
        else:
            console.success(result.output or "done")
