from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError

from morph.settings import MorphSettings


@click.group(help="File conversion toolkit")
@buvis_options(settings_class=MorphSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("html2md", help="Convert HTML files to Markdown")
@click.argument("directory", type=click.Path(exists=True))
def html2md(directory: str) -> None:
    try:
        from morph.commands.html2md.html2md import CommandHtml2Md
    except ImportError:
        console.require_import("morph")
        return

    console.report_result(CommandHtml2Md(directory=directory).execute())


@cli.command("deblank", help="Remove blank pages from PDFs")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
def deblank(files: tuple[str, ...]) -> None:
    from morph.commands.deblank.deblank import CommandDeblank

    try:
        cmd = CommandDeblank(files=files)
        result = cmd.execute()
    except FatalError as error:
        console.panic(str(error))
        return

    console.report_result(result)


if __name__ == "__main__":
    cli()
