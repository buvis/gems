from __future__ import annotations

import os

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from buvis.pybase.result import FatalError

from outlookctl.settings import OutlookctlSettings


@click.group(help="CLI to Outlook")
@buvis_options(settings_class=OutlookctlSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("create_timeblock")
@click.pass_context
def create_timeblock(ctx: click.Context) -> None:
    if os.name != "nt":
        console.panic("OutlookLocalAdapter only available on Windows")
        return

    from outlookctl.commands.create_timeblock.create_timeblock import CommandCreateTimeblock

    settings = get_settings(ctx, OutlookctlSettings)

    try:
        cmd = CommandCreateTimeblock(duration=settings.default_timeblock_duration)
        result = cmd.execute()
    except FatalError as e:
        console.panic(str(e))
        return

    if result.success:
        console.print(result.output or "Done", mode="raw")
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
