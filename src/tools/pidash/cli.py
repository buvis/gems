from __future__ import annotations

import time
from pathlib import Path

import click


@click.command(help="Read-only TUI dashboard for autopilot PRD cycle progress")
@click.argument(
    "project_path",
    default=None,
    required=False,
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.option("--cleanup", is_flag=True, help="Remove session files older than 24h")
def cli(project_path: str | None, cleanup: bool) -> None:
    if cleanup:
        _cleanup_sessions()
        return

    try:
        from textual import __version__ as _t  # noqa: F401
        from watchfiles import __version__ as _w  # noqa: F401
    except ImportError:
        click.echo("pidash requires the 'pidash' extra: pip install buvis-gems[pidash]")
        raise SystemExit(1)

    from pidash.tui.app import PidashApp

    if project_path is not None:
        app = PidashApp(project_path=Path(project_path))
    else:
        _auto_cleanup_sessions()
        app = PidashApp()
    app.run()


def _cleanup_sessions(max_age_hours: int = 24, *, quiet: bool = False) -> None:
    from pidash.tui.watcher import SESSIONS_DIR

    if not SESSIONS_DIR.is_dir():
        if not quiet:
            click.echo("No sessions directory found.")
        return

    now = time.time()
    removed = 0
    for f in SESSIONS_DIR.glob("*.json"):
        age_hours = (now - f.stat().st_mtime) / 3600
        if age_hours > max_age_hours:
            f.unlink()
            removed += 1
    if not quiet:
        click.echo(f"Removed {removed} stale session file(s).")


def _auto_cleanup_sessions() -> None:
    _cleanup_sessions(quiet=True)


if __name__ == "__main__":
    cli()
