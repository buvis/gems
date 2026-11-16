from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import get_settings
from rich.markup import escape

from bim.commands.tx.shared.format import CONCEPT_NOTE_TYPES, ConceptType
from bim.settings import BimSettings

if TYPE_CHECKING:
    from bim.commands.tx.shared.paths import TiromexPaths

__all__ = ["register_tx_group"]

_ZETTEL_TYPES = [value for value in CONCEPT_NOTE_TYPES if value != "wiki-article"]
_CONCEPT_TYPES = [member.value for member in ConceptType]


def register_tx_group(cli: click.Group) -> None:
    cli.add_command(tx)


def _resolve_paths(settings: BimSettings) -> TiromexPaths | None:
    """Return the tiromex paths, or panic (exit 1) on a bad folder setting."""
    from bim.dependencies import get_tiromex_paths

    try:
        return get_tiromex_paths(settings)
    except ValueError as exc:
        console.panic(escape(str(exc)))
        return None


def _warn_stderr(warnings: list[str]) -> None:
    for message in warnings:
        console.warning(escape(message), stderr=True)


def _out(text: str) -> None:
    """Write a machine-read payload on stdout: no markers, no markup, no wrapping."""
    console.console.out(text, highlight=False)


@click.group("tx", help="Tiromex: the concept notes in the tiromex folder")
def tx() -> None:
    """Group of tiromex commands."""


def _warn_if_overdue(ctx: click.Context) -> None:
    """Warn once on stderr when maintenance is overdue (``status`` shows it itself).

    Runs inside each command callback, so an eager ``--help`` exits before it.
    """
    from bim.commands.tx.status import staleness

    settings = get_settings(ctx, BimSettings)
    reason, days = staleness(dt.datetime.now().astimezone(), settings.tx.maintenance_window_days)
    wording = {
        "never": "maintenance has never run",
        "unparseable": "maintenance state is unreadable",
        "stale": f"maintenance is stale: last run {days}d ago",
    }
    if reason in wording:
        console.warning(wording[reason], stderr=True)


@tx.command("new", help="Create one note in the tiromex folder and print its path")
@click.option("--title", "title", required=True, help="Note title (also the H1)")
@click.option("--type", "zettel_type", type=click.Choice(_ZETTEL_TYPES), default="note", show_default=True)
@click.option("--concept-type", "concept_type", type=click.Choice(_CONCEPT_TYPES), default=None)
@click.pass_context
def tx_new(ctx: click.Context, title: str, zettel_type: str, concept_type: str | None) -> None:
    from bim.commands.tx.new import CommandTxNew
    from bim.dependencies import get_repo

    _warn_if_overdue(ctx)
    paths = _resolve_paths(get_settings(ctx, BimSettings))
    if paths is None:
        return
    result = CommandTxNew(paths, get_repo(), title=title, zettel_type=zettel_type, concept_type=concept_type).execute()
    if not result.success:
        console.report_result(result, literal=True)
        ctx.exit(1)
    _out(result.output or "")


@tx.command("validate", help="Check every note in the tiromex folder")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print a JSON report on stdout")
@click.pass_context
def tx_validate(ctx: click.Context, *, as_json: bool) -> None:
    from bim.commands.tx.validate import CommandTxValidate

    _warn_if_overdue(ctx)
    settings = get_settings(ctx, BimSettings)
    paths = _resolve_paths(settings)
    if paths is None:
        return
    result = CommandTxValidate(paths, as_json=as_json, max_body_lines=settings.tx.max_zettel_body_lines).execute()
    if as_json:
        _warn_stderr(result.warnings)
        _out(result.output or "")
    else:
        console.report_result(result, literal=True)
    if not result.success:
        ctx.exit(1)


@tx.command("export-claims", help="Print the claim index as JSON, or write it with --out")
@click.option("--out", "out", type=click.Path(path_type=Path), default=None, help="Write the JSON to this file")
@click.pass_context
def tx_export_claims(ctx: click.Context, out: Path | None) -> None:
    from bim.commands.tx.export_claims import CommandTxExportClaims

    _warn_if_overdue(ctx)
    paths = _resolve_paths(get_settings(ctx, BimSettings))
    if paths is None:
        return
    result = CommandTxExportClaims(paths, out=out).execute()
    _warn_stderr(result.warnings)
    if not result.success:
        console.failure(escape(result.error or "export-claims failed"), stderr=True)
        ctx.exit(1)
    _out(result.output or "")


@tx.command("status", help="Print the tiromex dashboard")
@click.pass_context
def tx_status(ctx: click.Context) -> None:
    from bim.commands.tx.status import CommandTxStatus

    settings = get_settings(ctx, BimSettings)
    paths = _resolve_paths(settings)
    if paths is None:
        return
    result = CommandTxStatus(
        paths,
        maintenance_window_days=settings.tx.maintenance_window_days,
        prune_window_days=settings.tx.prune_window_days,
        pruning_enabled=settings.tx.pruning_enabled,
    ).execute()
    if not result.success:
        console.report_result(result, literal=True)
        ctx.exit(1)
    _warn_stderr(result.warnings)
    _out(result.output or "")
