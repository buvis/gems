from __future__ import annotations

from pathlib import Path

import click


@click.command(help="Read-only TUI dashboard for autopilot PRD cycle progress")
@click.argument(
    "project_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
def cli(project_path: str) -> None:
    try:
        from textual import __version__ as _  # noqa: F401
    except ImportError:
        click.echo("pidash requires the 'pidash' extra: pip install buvis-gems[pidash]")
        raise SystemExit(1)

    from pidash.tui.app import PidashApp

    app = PidashApp(project_path=Path(project_path))
    app.run()


if __name__ == "__main__":
    cli()
