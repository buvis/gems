from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from buvis.pybase.result import FatalError

from puc.settings import PucSettings


@click.group(help="Photo utility collection")
@buvis_options(settings_class=PucSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("strip", help="Strip EXIF metadata from photos, keeping copyright and dates")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.pass_context
def strip(ctx: click.Context, files: tuple[str, ...]) -> None:
    settings = get_settings(ctx, PucSettings)

    from puc.commands.strip.strip import CommandStrip

    cmd = CommandStrip(files=files, keep_tags=settings.strip_keep_tags)
    try:
        with console.status(f"Stripping metadata from {len(files)} file(s)"):
            result = cmd.execute()
    except FatalError as e:
        console.panic(str(e))
        return

    for w in result.warnings:
        console.warning(w)
    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
