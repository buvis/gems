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
        jira_adapter: dict[str, Any] = (global_settings.model_extra or {}).get("jira_adapter", {})
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
@click.option("-l", "--list", "list_templates", is_flag=True, default=False, help="List available templates")
@click.pass_context
def create_note(
    ctx: click.Context,
    zettel_type: str | None,
    title: str | None,
    tags: str | None,
    answer: tuple[str, ...],
    *,
    list_templates: bool,
) -> None:
    if list_templates:
        from buvis.pybase.zettel.domain.templates import discover_templates
        from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval

        for name in sorted(discover_templates(python_eval)):
            console.print(name, mode="raw")
        return

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
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.option("-e", "--edit", is_flag=True, default=False, help="Pick result with fzf and open in nvim")
@click.option("-l", "--list", "list_queries", is_flag=True, default=False, help="List available queries")
@click.pass_context
def query(
    ctx: click.Context,
    query_file: str | None,
    query_string: str | None,
    *,
    edit: bool,
    list_queries: bool,
) -> None:
    if list_queries:
        from bim.commands.query.query import BUNDLED_QUERY_DIR
        from buvis.pybase.zettel.infrastructure.query.query_spec_parser import list_query_files

        for name, path in sorted(list_query_files(bundled_dir=BUNDLED_QUERY_DIR).items()):
            console.print(f"{name:30s} {path}", mode="raw")
        return

    from bim.commands.query.query import CommandQuery

    settings = get_settings(ctx, BimSettings)
    cmd = CommandQuery(
        default_directory=str(Path(settings.path_zettelkasten).expanduser().resolve()),
        archive_directory=str(Path(settings.path_archive).expanduser().resolve()),
        file=query_file,
        query=query_string,
        edit=edit,
    )
    cmd.execute()


@cli.command("edit", help="Edit zettel metadata")
@click.argument("path_to_note")
@click.option("--title", default=None, help="New title")
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option("--type", "zettel_type", default=None, help="Note type")
@click.option("--processed/--no-processed", default=None, help="Processed flag")
@click.option("--publish/--no-publish", default=None, help="Publish flag")
@click.option("-s", "--set", "extra_sets", multiple=True, help="Arbitrary key=value metadata")
def edit_note(
    path_to_note: str,
    title: str | None,
    tags: str | None,
    zettel_type: str | None,
    processed: bool | None,
    publish: bool | None,
    extra_sets: tuple[str, ...],
) -> None:
    path = Path(path_to_note)
    if not path.is_file():
        console.failure(f"{path_to_note} doesn't exist")
        return

    changes: dict[str, Any] = {}
    if title is not None:
        changes["title"] = title
    if tags is not None:
        changes["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if zettel_type is not None:
        changes["type"] = zettel_type
    if processed is not None:
        changes["processed"] = processed
    if publish is not None:
        changes["publish"] = publish
    for s in extra_sets:
        if "=" in s:
            k, v = s.split("=", 1)
            changes[k] = v

    from bim.commands.edit_note.edit_note import CommandEditNote

    cmd = CommandEditNote(path=path, changes=changes or None)
    cmd.execute()


@cli.command("archive", help="Archive zettel(s): set processed + move to archive dir")
@click.argument("paths", nargs=-1, required=True)
@click.option("--undo", is_flag=True, default=False, help="Unarchive (move back to zettelkasten)")
@click.pass_context
def archive_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    *,
    undo: bool,
) -> None:
    from bim.commands.archive_note.archive_note import CommandArchiveNote

    settings = get_settings(ctx, BimSettings)
    cmd = CommandArchiveNote(
        paths=[Path(p) for p in paths],
        path_archive=Path(settings.path_archive).expanduser().resolve(),
        path_zettelkasten=Path(settings.path_zettelkasten).expanduser().resolve(),
        undo=undo,
    )
    cmd.execute()


@cli.command("show", help="Display zettel content")
@click.argument("path_to_note")
def show_note(path_to_note: str) -> None:
    path = Path(path_to_note)
    if not path.is_file():
        console.failure(f"{path_to_note} doesn't exist")
        return
    from bim.commands.show_note.show_note import CommandShowNote

    cmd = CommandShowNote(path=path)
    cmd.execute()


@cli.command("serve", help="Start web dashboard")
@click.option("-p", "--port", default=8000, type=int)
@click.option("-H", "--host", default="127.0.0.1")
@click.option("--no-browser", is_flag=True, default=False)
@click.pass_context
def serve(
    ctx: click.Context,
    port: int,
    host: str,
    *,
    no_browser: bool,
) -> None:
    from bim.commands.serve.serve import CommandServe

    settings = get_settings(ctx, BimSettings)
    cmd = CommandServe(
        default_directory=str(Path(settings.path_zettelkasten).expanduser().resolve()),
        archive_directory=str(Path(settings.path_archive).expanduser().resolve()),
        host=host,
        port=port,
        no_browser=no_browser,
    )
    cmd.execute()


if __name__ == "__main__":
    cli()
