"""Click registration for ``bim doc rules`` subcommands."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import get_settings

from bim.settings import BimSettings

__all__ = ["register_rules_subcommands"]


def register_rules_subcommands(doc_group: click.Group) -> None:
    """Attach the ``bim doc rules`` command group to ``doc_group``."""
    doc_group.add_command(doc_rules)


@click.group("rules", help="Rule engine authoring + diagnostics")
@click.pass_context
def doc_rules(ctx: click.Context) -> None:
    """Author and verify per-issuer extraction rules."""


@doc_rules.command("list", help="List all rules across issuers")
@click.pass_context
def doc_rules_list(ctx: click.Context) -> None:
    settings = get_settings(ctx, BimSettings)
    if settings.doc is None:
        console.panic("[doc] section missing in bim config; configure paths.business_root etc. first")
        return
    try:
        from bim.commands.doc.rules.list import CommandRulesList
        from bim.dependencies import get_issuer_registry
    except ImportError:
        console.require_import("doc")
        return
    bundle = get_issuer_registry(settings.doc)
    result = CommandRulesList().run(bundle.registry)
    if not result.success:
        console.failure(result.error or "list failed")
        return
    console.info(result.output or "")


@doc_rules.command("validate", help="Statically validate rule blocks in issuers.yml")
@click.pass_context
def doc_rules_validate(ctx: click.Context) -> None:
    settings = get_settings(ctx, BimSettings)
    if settings.doc is None:
        console.panic("[doc] section missing in bim config; configure paths.business_root etc. first")
        return
    try:
        from bim.commands.doc.rules.validate import CommandRulesValidate
    except ImportError:
        console.require_import("doc")
        return
    # Validate is the command users run *to diagnose* a malformed
    # issuers.yml. Loading via ``get_issuer_registry`` here would raise on
    # the exact failure modes we want to report (uncompilable regex,
    # unknown transform, reserved-field, duplicate id). Pass the path
    # directly; the command class catches loader errors itself.
    issuers_file = settings.doc.paths.issuers_file
    if issuers_file is None:
        console.panic("[doc] paths.issuers_file is not set")
        return
    result = CommandRulesValidate().run(issuers_file)
    if not result.success:
        console.panic(result.error or "validate failed")
        return
    console.success(result.output or "OK")


@doc_rules.command("test", help="Run a single rule against a single PDF (read-only)")
@click.argument("rule_id")
@click.option(
    "--pdf",
    "pdf_path",
    required=True,
    type=click.Path(path_type=Path),
    help="Path to the PDF to test against",
)
@click.pass_context
def doc_rules_test(ctx: click.Context, rule_id: str, pdf_path: Path) -> None:
    if not pdf_path.is_file():
        console.panic(f"file not found: {pdf_path}")
        return
    settings = get_settings(ctx, BimSettings)
    if settings.doc is None:
        console.panic("[doc] section missing in bim config; configure paths.business_root etc. first")
        return
    try:
        from bim.commands.doc.rules.test import CommandRulesTest
        from bim.dependencies import get_issuer_registry, get_ocr_runner
    except ImportError:
        console.require_import("doc")
        return
    bundle = get_issuer_registry(settings.doc)
    result = CommandRulesTest(ocr_runner=get_ocr_runner(settings.doc)).run(bundle.registry, rule_id, pdf_path)
    if not result.success:
        # PRD acceptance: "Exit 0 on match, non-zero on no-match." console.panic
        # prints the failure body (clause-by-clause result, "Result: NO MATCH")
        # and exits 1 - same styling as console.failure plus the required
        # non-zero exit code.
        console.panic(result.error or "rule test failed")
        return
    console.info(result.output or "")
    console.success("MATCH")


@doc_rules.command(
    "backtest",
    help=(
        "Walk the archive and report per-rule match counts. Read-only; OCRs "
        "PDFs on demand so it can be slow on large archives."
    ),
)
@click.option("--rule", "rule_id", default=None, help="Restrict to a single rule id")
@click.option("--issuer", "issuer_slug", default=None, help="Restrict to a single issuer slug")
@click.pass_context
def doc_rules_backtest(ctx: click.Context, rule_id: str | None, issuer_slug: str | None) -> None:
    settings = get_settings(ctx, BimSettings)
    if settings.doc is None:
        console.panic("[doc] section missing in bim config; configure paths.business_root etc. first")
        return
    try:
        from bim.commands.doc.rules.backtest import CommandRulesBacktest
        from bim.commands.doc.shared.progress import NoOpProgressReporter, SpinnerProgressReporter
        from bim.dependencies import get_issuer_registry, get_ocr_runner
    except ImportError:
        console.require_import("doc")
        return
    bundle = get_issuer_registry(settings.doc)
    # Show a Rich spinner with per-PDF progress in interactive runs; the
    # archive can hold 1k+ PDFs and OCR runs on demand, so silent walking
    # looks hung. Stay silent when stdout is piped/redirected so scripts
    # see only the final summary line.
    reporter = SpinnerProgressReporter(console) if sys.stdout.isatty() else NoOpProgressReporter()
    with reporter:
        result = CommandRulesBacktest(ocr_runner=get_ocr_runner(settings.doc)).run(
            bundle.registry,
            settings.doc.paths.business_root,
            rule_id=rule_id,
            issuer_slug=issuer_slug,
            progress=reporter,
        )
    if not result.success:
        console.failure(result.error or "backtest failed")
        return
    console.info(result.output or "")
