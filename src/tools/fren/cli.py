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
        console.require_import("fren")
        return

    console.report_result(CommandSlug(paths=paths).execute())


@cli.command("directorize", help="Wrap files in directories named after file stem")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
def directorize(directory: str) -> None:
    from fren.commands.directorize.directorize import CommandDirectorize

    console.report_result(CommandDirectorize(directory=directory).execute())


@cli.command("flatten", help="Copy nested files into flat destination")
@click.argument("source", type=click.Path(exists=True, file_okay=False))
@click.argument("destination", type=click.Path(file_okay=False))
def flatten(source: str, destination: str) -> None:
    from fren.commands.flatten.flatten import CommandFlatten

    console.report_result(CommandFlatten(source=source, destination=destination).execute())


@cli.command("normalize", help="NFC-normalize directory names")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
def normalize(directory: str) -> None:
    from fren.commands.normalize.normalize import CommandNormalize

    console.report_result(CommandNormalize(directory=directory).execute())


if __name__ == "__main__":
    cli()
