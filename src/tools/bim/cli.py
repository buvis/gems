from __future__ import annotations

from pathlib import Path
from typing import Any

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import GlobalSettings, buvis_options, get_settings

from bim.settings import BimSettings


@click.group(help="CLI to BUVIS InfoMesh")
@buvis_options(settings_class=BimSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("import", help="Import a note to zettelkasten")
@click.argument("path_to_note")
@click.pass_context
def import_note(
    ctx: click.Context,
    path_to_note: Path,
) -> None:
    if Path(path_to_note).is_file():
        from bim.commands.import_note.import_note import CommandImportNote

        settings = get_settings(ctx, BimSettings)
        cmd = CommandImportNote(
            path_note=Path(path_to_note),
            path_zettelkasten=Path(settings.path_zettelkasten).expanduser().resolve(),
        )
        cmd.execute()
    else:
        console.failure(f"{path_to_note} doesn't exist")


@cli.command("format", help="Format a note")
@click.argument("path_to_note")
@click.option(
    "-h",
    "--highlight",
    is_flag=True,
    show_default=True,
    default=False,
    help="Highlight formatted content",
)
@click.option(
    "-d",
    "--diff",
    is_flag=True,
    show_default=True,
    default=False,
    help="Show original and formatted note side by side if different",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False, writable=True, resolve_path=True),
)
def format_note(
    path_to_note: Path,
    *,
    highlight: bool,
    diff: bool,
    output: None | Path,
) -> None:
    if Path(path_to_note).is_file():
        from bim.commands.format_note.format_note import CommandFormatNote

        cmd = CommandFormatNote(
            path_note=Path(path_to_note),
            is_highlighting_requested=highlight,
            is_diff_requested=diff,
            path_output=Path(output) if output else None,
        )
        cmd.execute()
    else:
        console.failure(f"{path_to_note} doesn't exist")


@cli.command("sync", help="Synchronize note with external system")
@click.argument("path_to_note")
@click.argument("target_system")
@click.pass_context
def sync_note(
    ctx: click.Context,
    path_to_note: Path,
    target_system: str,
) -> None:
    if Path(path_to_note).is_file():
        from bim.commands.sync_note.sync_note import CommandSyncNote

        global_settings = get_settings(ctx, GlobalSettings)
        jira_adapter: dict[str, Any] = global_settings.model_extra.get("jira_adapter", {})
        cmd = CommandSyncNote(
            path_note=Path(path_to_note),
            target_system=target_system,
            jira_adapter_config=jira_adapter,
        )
        cmd.execute()
    else:
        console.failure(f"{path_to_note} doesn't exist")


@cli.command("parse_tags", help="Parse Obsidian Metadata Extractor tags.json")
@click.argument("path_to_tags_json")
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=True, dir_okay=False, writable=True, resolve_path=True),
)
def parse_tags(
    path_to_tags_json: Path,
    *,
    output: None | Path,
) -> None:
    if Path(path_to_tags_json).is_file():
        from bim.commands.parse_tags.parse_tags import CommandParseTags

        cmd = CommandParseTags(
            path_tags_json=Path(path_to_tags_json),
            path_output=Path(output) if output else None,
        )
        cmd.execute()
    else:
        console.failure(f"{path_to_tags_json} doesn't exist")


@cli.command("create", help="Create a new zettel from template")
@click.option("-t", "--type", "zettel_type", default=None, help="Template type (note, project)")
@click.option("--title", default=None, help="Zettel title")
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option("-a", "--answer", multiple=True, help="Template question answer as key=value")
@click.pass_context
def create_note(
    ctx: click.Context,
    zettel_type: str | None,
    title: str | None,
    tags: str | None,
    answer: tuple[str, ...],
) -> None:
    from bim.commands.create_note.create_note import CommandCreateNote

    settings = get_settings(ctx, BimSettings)
    extra_answers: dict[str, str] = {}
    for a in answer:
        if "=" in a:
            k, v = a.split("=", 1)
            extra_answers[k] = v
    cmd = CommandCreateNote(
        path_zettelkasten=Path(settings.path_zettelkasten).expanduser().resolve(),
        zettel_type=zettel_type,
        title=title,
        tags=tags,
        extra_answers=extra_answers,
    )
    cmd.execute()


@cli.command("query", help="Query zettels with YAML filter/sort/output spec")
@click.option("-f", "--file", "query_file", default=None, help="Path to YAML query spec file")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.pass_context
def query(
    ctx: click.Context,
    query_file: str | None,
    query_string: str | None,
) -> None:
    from bim.commands.query.query import CommandQuery

    settings = get_settings(ctx, BimSettings)
    cmd = CommandQuery(
        default_directory=str(Path(settings.path_zettelkasten).expanduser().resolve()),
        file=query_file,
        query=query_string,
    )
    cmd.execute()


if __name__ == "__main__":
    cli()
