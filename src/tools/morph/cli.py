from __future__ import annotations

from pathlib import Path

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
@click.argument("directory", type=click.Path())
def html2md(directory: str) -> None:
    if not Path(directory).is_dir():
        console.panic(f"directory not found: {directory}")
        return

    try:
        from morph.commands.html2md.html2md import CommandHtml2Md
    except ImportError:
        console.require_import("morph")
        return

    console.report_result(CommandHtml2Md(directory=directory).execute())


@cli.command("deblank", help="Remove blank pages from PDFs")
@click.argument("files", nargs=-1, required=True, type=click.Path())
def deblank(files: tuple[str, ...]) -> None:
    for f in files:
        if not Path(f).is_file():
            console.panic(f"file not found: {f}")
            return

    from morph.commands.deblank.deblank import CommandDeblank

    try:
        cmd = CommandDeblank(files=files)
        result = cmd.execute()
    except FatalError as error:
        console.panic(str(error))
        return

    console.report_result(result)


@cli.command("pdf2png", help="Convert PDF pages into one stacked PNG")
@click.argument("files", nargs=-1, required=True, type=click.Path())
@click.option("--dpi", default=200, show_default=True, help="Render resolution in DPI")
def pdf2png(files: tuple[str, ...], dpi: int) -> None:
    for f in files:
        if not Path(f).is_file():
            console.panic(f"file not found: {f}")
            return

    try:
        from morph.commands.pdf2png.pdf2png import CommandPdf2Png
    except ImportError:
        console.require_import("morph")
        return

    try:
        cmd = CommandPdf2Png(files=files, dpi=dpi)
        result = cmd.execute()
    except FatalError as error:
        console.panic(str(error))
        return

    console.report_result(result)


if __name__ == "__main__":
    cli()
