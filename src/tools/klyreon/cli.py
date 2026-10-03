"""Klyreon CLI group.

Every command renders a :class:`CommandResult` through ``console``; command
classes never call ``console`` or ``sys.exit`` themselves. The group callback
emits the maintenance-staleness warning once per invocation (best-effort: it
stays silent when no vault root is resolvable yet, e.g. before ``init``).
"""

from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings

from klyreon.settings import KlyreonSettings

_ZETTEL_TYPES = ["note", "definition", "procedure", "wiki-article", "cheatsheet", "snippet", "course", "ai-prompt"]
_CONCEPT_TYPES = ["thesis", "argument", "aporia", "question", "example", "observation"]
_OPERATORS = ["claude"]


@click.group(help="Autonomous Memex-Zettelkasten")
@buvis_options(settings_class=KlyreonSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    _warn_if_maintenance_stale(ctx)


def _warn_stale(message: str) -> None:
    """Emit a diagnostic warning to STDERR, keeping stdout pure for machine output.

    The staleness notice fires on every command (PRD requirement); routing it to
    stderr means ``validate --json`` / ``export-claims`` stdout stays valid for
    ``jq`` while a terminal user still sees the warning.
    """
    from rich.console import Console

    Console(stderr=True).print(f" \u26a0 [light_goldenrod3]{message}[/light_goldenrod3]")


def _warn_if_maintenance_stale(ctx: click.Context) -> None:
    """Emit the staleness warning for every command, if a root is resolvable."""
    from klyreon.vault.config import RootError, resolve_root
    from klyreon.vault.state import read_state

    try:
        resolve_root()
    except RootError:
        return  # no vault yet (pre-init); nothing to warn about.

    settings = get_settings(ctx, KlyreonSettings)
    import datetime as dt

    last = read_state().get("last_maintain")
    now = dt.datetime.now().astimezone()
    window = dt.timedelta(days=settings.maintenance_window_days)
    if not last:
        _warn_stale("maintenance has never run (run the maintain command once it ships)")
        return
    try:
        parsed = dt.datetime.fromisoformat(last)
    except (TypeError, ValueError):
        _warn_stale("maintenance state is unreadable")
        return
    if now - parsed > window:
        _warn_stale(f"maintenance is stale: last run {(now - parsed).days}d ago")


def _resolve_root_or_panic() -> Path:
    from klyreon.vault.config import RootError, resolve_root

    try:
        return resolve_root()
    except RootError as exc:
        console.panic(str(exc))
        raise  # unreachable: panic exits


@cli.command("init", help="Create the vault skeleton and the config that points at it")
@click.argument("path", required=False, type=click.Path(file_okay=False, path_type=Path))
@click.option("--force", is_flag=True, default=False, help="Overwrite a config that points elsewhere.")
@click.option(
    "--operator",
    "operators",
    multiple=True,
    type=click.Choice(_OPERATORS),
    help="Install this operator's asset pack without prompting (repeatable).",
)
@click.option("--no-input", "no_input", is_flag=True, default=False, help="Skip the interactive asset-install offer.")
@click.pass_context
def init(ctx: click.Context, path: Path | None, *, force: bool, operators: tuple[str, ...], no_input: bool) -> None:
    import sys

    from klyreon.commands.init import AssetOffer, CommandInit

    target = path if path is not None else Path.cwd()
    is_tty = sys.stdin.isatty()
    offer = AssetOffer(
        operators=list(operators),
        no_input=no_input,
        is_tty=is_tty,
        confirm=console.confirm,
    )
    result = CommandInit(target, force=force, offer=offer).execute()
    console.report_result(result)
    if not result.success:
        ctx.exit(1)


@cli.command("new", help="Create one spec-valid zettel with a unique ID")
@click.option("--title", required=True, help="Zettel title (also the H1).")
@click.option("--type", "zettel_type", default="note", type=click.Choice(_ZETTEL_TYPES), help="Zettel type.")
@click.option(
    "--concept-type",
    "concept_type",
    default=None,
    type=click.Choice(_CONCEPT_TYPES),
    help="Make it a concept zettel of this epistemic shape.",
)
@click.pass_context
def new(ctx: click.Context, title: str, zettel_type: str, concept_type: str | None) -> None:
    from klyreon.commands.new import CommandNew

    root = _resolve_root_or_panic()
    result = CommandNew(root, zettel_type=zettel_type, title=title, concept_type=concept_type).execute()
    console.report_result(result, on_success=lambda r: console.print(r.output or "", mode="raw"))
    if not result.success:
        ctx.exit(1)


@cli.command("validate", help="Run every mechanical check over the whole vault")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine-readable report.")
@click.pass_context
def validate(ctx: click.Context, *, as_json: bool) -> None:
    from klyreon.commands.validate import CommandValidate

    root = _resolve_root_or_panic()
    settings = get_settings(ctx, KlyreonSettings)
    result = CommandValidate(root, as_json=as_json, max_body_lines=settings.max_zettel_body_lines).execute()
    if as_json:
        console.print(result.output or "", mode="raw")
    else:
        console.report_result(result)
    if not result.success:
        ctx.exit(1)


@cli.command("export-claims", help="Emit the claim index as JSON")
@click.option(
    "--out",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write JSON here instead of stdout (refused if under the vault root).",
)
@click.pass_context
def export_claims(ctx: click.Context, out: Path | None) -> None:
    from klyreon.commands.export_claims import CommandExportClaims

    root = _resolve_root_or_panic()
    result = CommandExportClaims(root, out=out).execute()
    if result.success and out is None:
        console.print(result.output or "", mode="raw")
        for w in result.warnings:
            console.warning(w)
    else:
        console.report_result(result)
    if not result.success:
        ctx.exit(1)


@cli.command("status", help="Print the vault dashboard")
@click.pass_context
def status(ctx: click.Context) -> None:
    from klyreon.commands.status import CommandStatus

    root = _resolve_root_or_panic()
    settings = get_settings(ctx, KlyreonSettings)
    result = CommandStatus(root, maintenance_window_days=settings.maintenance_window_days, check_assets=True).execute()
    console.report_result(result, on_success=lambda r: console.print(r.output or "", mode="raw"))
    if not result.success:
        ctx.exit(1)


@cli.group("assets", help="Install, refresh, inspect, and remove operator asset packs")
def assets() -> None:
    """Operator asset packs — the knowledge an interactive session needs."""


@assets.command("install", help="Install (or refresh) one or more operator packs")
@click.option(
    "--operator",
    "operators",
    multiple=True,
    help="Operator to install (repeatable). Default: every operator already installed.",
)
@click.pass_context
def assets_install(ctx: click.Context, operators: tuple[str, ...]) -> None:
    from klyreon.commands.assets import CommandAssetsInstall

    result = CommandAssetsInstall(list(operators)).execute()
    console.report_result(result)
    if not result.success:
        ctx.exit(1)


@assets.command("status", help="Show what is installed and whether it is current")
@click.pass_context
def assets_status(ctx: click.Context) -> None:
    from klyreon.commands.assets import CommandAssetsStatus

    result = CommandAssetsStatus().execute()
    console.report_result(result, on_success=lambda r: console.print(r.output or "", mode="raw"))
    if not result.success:
        ctx.exit(1)


@assets.command("refresh", help="Re-install every operator recorded in the manifest")
@click.pass_context
def assets_refresh(ctx: click.Context) -> None:
    from klyreon.commands.assets import CommandAssetsRefresh

    result = CommandAssetsRefresh().execute()
    console.report_result(result)
    if not result.success:
        ctx.exit(1)


@assets.command("uninstall", help="Remove klyreon's files; keep edited ones")
@click.option(
    "--operator",
    "operators",
    multiple=True,
    help="Operator to uninstall (repeatable). Default: every operator installed.",
)
@click.pass_context
def assets_uninstall(ctx: click.Context, operators: tuple[str, ...]) -> None:
    from klyreon.commands.assets import CommandAssetsUninstall

    result = CommandAssetsUninstall(list(operators)).execute()
    console.report_result(result)
    if not result.success:
        ctx.exit(1)


if __name__ == "__main__":
    cli()
