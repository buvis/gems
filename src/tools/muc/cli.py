from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from buvis.pybase.filesystem import DirTree

from muc.settings import MucSettings

ALERT_FILE_COUNT = 100
ALERT_DIR_DEPTH = 3


@click.group(help="Tools for music collection management")
@buvis_options(settings_class=MucSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("limit", help="Limit audio file")
@click.option(
    "-o",
    "--output",
    default=None,
    help="Transcoded files output directory.",
)
@click.argument("source_directory")
@click.pass_context
def limit(ctx: click.Context, source_directory: str, output: str | None = None) -> None:
    settings = get_settings(ctx, MucSettings)

    path_source = Path(source_directory).resolve()
    if not path_source.is_dir():
        console.panic(f"{source_directory} isn't a directory")

    path_output = Path(output).resolve() if output else Path.cwd() / "transcoded"
    path_output.mkdir(exist_ok=True)

    try:
        from muc.commands.limit.limit import CommandLimit
    except ImportError:
        console.panic("muc requires the 'muc' extra. Install with: uv tool install buvis-gems[muc]")
        return

    cmd = CommandLimit(
        source_dir=path_source,
        output_dir=path_output,
        bitrate=settings.limit_flac_bitrate,
        bit_depth=settings.limit_flac_bit_depth,
        sampling_rate=settings.limit_flac_sampling_rate,
    )
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


@cli.command("tidy", help="Tidy directory")
@click.option("-y", "--yes", is_flag=True, default=False, help="Skip confirmation prompt.")
@click.argument("directory")
@click.pass_context
def tidy(ctx: click.Context, directory: str, yes: bool) -> None:
    settings = get_settings(ctx, MucSettings)

    path_directory = Path(directory).resolve()
    if not path_directory.is_dir():
        console.panic(f"{path_directory} isn't a directory")

    file_count = DirTree.count_files(path_directory)
    max_depth = DirTree.get_max_depth(path_directory)

    if not yes and (file_count > ALERT_FILE_COUNT or max_depth > ALERT_DIR_DEPTH):
        message = (
            f"Warning: The directory contains {file_count} files "
            f"and has a maximum depth of {max_depth}. "
            "Do you want to proceed?"
        )
        click.confirm(message, abort=True)

    from muc.commands.tidy.tidy import CommandTidy

    cmd = CommandTidy(
        directory=path_directory,
        junk_extensions=settings.tidy_junk_extensions,
    )
    cmd.execute()


@cli.command("cover", help="Keep only the newest cover image per directory")
@click.argument("directory")
def cover(directory: str) -> None:
    path_directory = Path(directory).resolve()
    if not path_directory.is_dir():
        console.panic(f"{path_directory} isn't a directory")

    from muc.commands.cover.cover import CommandCover

    cmd = CommandCover(directory=path_directory)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
