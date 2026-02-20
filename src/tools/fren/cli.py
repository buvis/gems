from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options

from fren.settings import FrenSettings


@click.group(help="File renamer toolkit")
@buvis_options(settings_class=FrenSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("slug", help="Slugify filenames")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
def slug(paths: tuple[str, ...]) -> None:
    try:
        from fren.commands.slug.slug import CommandSlug
    except ImportError:
        console.panic("Missing deps. Install with: uv tool install buvis-gems[fren]")

    cmd = CommandSlug(paths=paths)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


@cli.command("directorize", help="Wrap files in directories named after file stem")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
def directorize(directory: str) -> None:
    from fren.commands.directorize.directorize import CommandDirectorize

    cmd = CommandDirectorize(directory=directory)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


@cli.command("flatten", help="Copy nested files into flat destination")
@click.argument("source", type=click.Path(exists=True, file_okay=False))
@click.argument("destination", type=click.Path(file_okay=False))
def flatten(source: str, destination: str) -> None:
    from fren.commands.flatten.flatten import CommandFlatten

    cmd = CommandFlatten(source=source, destination=destination)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


@cli.command("normalize", help="NFC-normalize directory names")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
def normalize(directory: str) -> None:
    from fren.commands.normalize.normalize import CommandNormalize

    cmd = CommandNormalize(directory=directory)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
