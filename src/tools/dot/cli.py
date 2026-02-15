from __future__ import annotations

import click
from buvis.pybase.configuration import buvis_options, get_settings

from dot.settings import DotSettings


@click.group(help="CLI for bare repo dotfiles")
@buvis_options(settings_class=DotSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("status", help="Report status")
def status() -> None:
    from dot.commands.status.status import CommandStatus

    cmd = CommandStatus()
    cmd.execute()


@cli.command("add", help="Add changes")
@click.argument("file_path", required=False)
@click.pass_context
def add(ctx: click.Context, file_path: str | None = None) -> None:
    settings = get_settings(ctx, DotSettings)

    # CLI overrides settings
    resolved_path = file_path if file_path is not None else settings.add_file_path

    from dot.commands.add.add import CommandAdd

    cmd = CommandAdd(file_path=resolved_path)
    cmd.execute()


if __name__ == "__main__":
    cli()
