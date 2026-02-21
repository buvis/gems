from __future__ import annotations

import shutil
from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options

from vuc.settings import VucSettings


@click.group(help="Video utility collection")
@buvis_options(settings_class=VucSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("multilang", help="List video files with multiple audio tracks")
@click.argument("directory")
@click.argument("output_csv")
def multilang(directory: str, output_csv: str) -> None:
    path_directory = Path(directory).resolve()
    if not path_directory.is_dir():
        console.panic(f"{path_directory} isn't a directory")

    if shutil.which("mediainfo") is None:
        console.panic(
            "mediainfo is required. Install with: brew install mediainfo (macOS) "
            "or apt install mediainfo (Debian/Ubuntu)."
        )

    from vuc.commands.multilang import CommandMultilang

    cmd = CommandMultilang(directory=path_directory, output_csv=Path(output_csv).resolve())
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
