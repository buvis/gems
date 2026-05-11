from __future__ import annotations

import time
from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import CommandResult

_DEFAULT_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

_HOOK_EVENTS = (
    "set-attention",
    "clear-attention",
    "cleanup-session",
    "update-tasks",
    "sync-agent-return",
)


def _launch_tui(project_path: Path | None) -> None:
    try:
        from textual import __version__ as _t  # noqa: F401
        from watchfiles import __version__ as _w  # noqa: F401
    except ImportError:
        console.require_import("pidash", "pidash")

    from pidash.tui.app import PidashApp

    if project_path is not None:
        app = PidashApp(project_path=project_path)
    else:
        _auto_cleanup_sessions()
        app = PidashApp()
    app.run()


def _validate_project_path(project_path: Path | None) -> Path | None:
    if project_path is not None and not project_path.is_dir():
        console.panic(f"project path not found: {project_path}")
    return project_path


@click.group(
    invoke_without_command=True,
    help="Read-only TUI dashboard for autopilot PRD cycle progress",
)
@buvis_options
@click.option(
    "--project-path",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
    help="Project root to watch (defaults to multi-session mode).",
)
@click.option("--cleanup", is_flag=True, help="Remove session files older than 24h")
@click.pass_context
def cli(ctx: click.Context, project_path: Path | None, cleanup: bool) -> None:
    if cleanup:
        _cleanup_sessions()
        return
    if ctx.invoked_subcommand is not None:
        return
    _launch_tui(_validate_project_path(project_path))


@cli.command("tui", help="Launch the dashboard TUI (default action)")
@click.argument(
    "project_path",
    default=None,
    required=False,
    type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
)
def tui(project_path: Path | None) -> None:
    _launch_tui(_validate_project_path(project_path))


@cli.group("hooks", help="Manage pidash Claude Code hooks")
def hooks() -> None:
    pass


@hooks.command("run", help="Run a bundled pidash hook by event name")
@click.argument("event", type=click.Choice(_HOOK_EVENTS))
def hooks_run(event: str) -> None:
    if event == "set-attention":
        from pidash.hooks.set_attention import main as _main
    elif event == "clear-attention":
        from pidash.hooks.clear_attention import main as _main
    elif event == "cleanup-session":
        from pidash.hooks.cleanup_session import main as _main
    elif event == "update-tasks":
        from pidash.hooks.update_tasks import main as _main
    else:  # sync-agent-return
        from pidash.hooks.sync_agent_return import main as _main
    _main()


_SETTINGS_OPT = click.option(
    "--settings-path",
    "settings_path",
    default=_DEFAULT_SETTINGS_PATH,
    type=click.Path(path_type=Path),
    show_default=True,
    help="Path to Claude Code settings.json.",
)


@hooks.command("install", help="Install pidash hooks into ~/.claude/settings.json")
@_SETTINGS_OPT
def hooks_install(settings_path: Path) -> None:
    from pidash.commands.hooks.install import CommandInstall

    result = CommandInstall(settings_path=settings_path).execute()
    console.report_result(result)
    if not result.success:
        raise SystemExit(1)


@hooks.command("uninstall", help="Remove pidash hooks from ~/.claude/settings.json")
@_SETTINGS_OPT
def hooks_uninstall(settings_path: Path) -> None:
    from pidash.commands.hooks.uninstall import CommandUninstall

    result = CommandUninstall(settings_path=settings_path).execute()
    console.report_result(result)
    if not result.success:
        raise SystemExit(1)


@hooks.command("status", help="Show pidash hook installation status")
@_SETTINGS_OPT
def hooks_status(settings_path: Path) -> None:
    from pidash.commands.hooks.status import CommandStatus

    result = CommandStatus(settings_path=settings_path).execute()
    console.report_result(result, on_failure=_render_status_failure)
    if result.success:
        for row in result.metadata.get("hooks", []):
            console.info(_format_status_row(row))
    else:
        raise SystemExit(1)


def _format_status_row(row: dict[str, object]) -> str:
    matcher = row.get("matcher")
    matcher_str = matcher if isinstance(matcher, str) else "(default)"
    event = row.get("event")
    run_event = row.get("run_event")
    glyph = "✓" if row.get("installed") else "✘"
    return f"{glyph} {event}/{matcher_str} → {run_event}"


def _render_status_failure(result: CommandResult) -> None:
    console.failure(result.error or "pidash hooks status: failure")
    for row in result.metadata.get("hooks", []):
        console.info(_format_status_row(row))


def _cleanup_sessions(max_age_hours: int = 24, *, quiet: bool = False) -> None:
    from pidash.hooks.session import SESSIONS_DIR

    if not SESSIONS_DIR.is_dir():
        if not quiet:
            console.info("No sessions directory found.")
        return

    now = time.time()
    removed = 0
    for f in SESSIONS_DIR.glob("*.json"):
        age_hours = (now - f.stat().st_mtime) / 3600
        if age_hours > max_age_hours:
            f.unlink()
            removed += 1
    if not quiet:
        console.success(f"Removed {removed} stale session file(s).")


def _auto_cleanup_sessions() -> None:
    _cleanup_sessions(quiet=True)


if __name__ == "__main__":
    cli()
