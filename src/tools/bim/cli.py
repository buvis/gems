from __future__ import annotations

from pathlib import Path
from typing import Any

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import GlobalSettings, buvis_options, get_settings

from bim.settings import BimSettings


def _resolve_paths(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
) -> list[Path] | None:
    """Resolve paths from explicit args or query flags. Returns None on error."""
    has_paths = len(paths) > 0
    has_query = query_file is not None or query_string is not None

    if has_paths and has_query:
        console.failure("Provide paths or -f/-q, not both")
        return None

    if has_query:
        from bim.commands.shared.query_paths import resolve_query_paths

        settings = get_settings(ctx, BimSettings)
        default_dir = str(Path(settings.path_zettelkasten).expanduser().resolve())
        return resolve_query_paths(query_file, query_string, default_dir)

    if has_paths:
        return [Path(p) for p in paths]

    console.failure("Provide paths or -f/-q")
    return None


@click.group(help="CLI to BUVIS InfoMesh")
@buvis_options(settings_class=BimSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("import", help="Import a note to zettelkasten")
@click.argument("paths", nargs=-1, required=True)
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option("--force", is_flag=True, default=False, help="Overwrite if target exists")
@click.option("--remove-original", is_flag=True, default=False, help="Delete source after import")
@click.pass_context
def import_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    tags: str | None,
    *,
    force: bool,
    remove_original: bool,
) -> None:
    from bim.commands.import_note.import_note import CommandImportNote

    settings = get_settings(ctx, BimSettings)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    scripted = tags is not None or force or remove_original

    if not scripted and len(paths) > 1:
        console.failure("interactive import requires a single path")
        return

    cmd = CommandImportNote(
        paths=[Path(p) for p in paths],
        path_zettelkasten=Path(settings.path_zettelkasten).expanduser().resolve(),
        tags=tag_list,
        force=force,
        remove_original=remove_original,
        scripted=scripted,
    )
    cmd.execute()


@cli.command("format", help="Format a note")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
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
@click.pass_context
def format_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    *,
    highlight: bool,
    diff: bool,
    output: None | Path,
) -> None:
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.format_note.format_note import CommandFormatNote

    cmd = CommandFormatNote(
        paths=resolved,
        is_highlighting_requested=highlight,
        is_diff_requested=diff,
        path_output=Path(output) if output else None,
    )
    cmd.execute()


@cli.command("sync", help="Synchronize note(s) with external system")
@click.argument("paths", nargs=-1, required=False)
@click.option("-t", "--target", "target_system", required=True, help="Target system (e.g. jira)")
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation for batch sync")
@click.pass_context
def sync_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    target_system: str,
    query_file: str | None,
    query_string: str | None,
    *,
    force: bool,
) -> None:
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.sync_note.sync_note import CommandSyncNote

    global_settings = get_settings(ctx, GlobalSettings)
    jira_adapter: dict[str, Any] = (global_settings.model_extra or {}).get("jira_adapter", {})
    try:
        cmd = CommandSyncNote(
            paths=resolved,
            target_system=target_system,
            jira_adapter_config=jira_adapter,
            force=force,
        )
        cmd.execute()
    except (ValueError, FileNotFoundError) as exc:
        console.panic(str(exc))
    except NotImplementedError:
        console.panic(f"Sync target '{target_system}' not supported")


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
@click.option(
    "-b",
    "--batch",
    "batch_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="YAML or CSV batch spec file",
)
@click.pass_context
def create_note(
    ctx: click.Context,
    zettel_type: str | None,
    title: str | None,
    tags: str | None,
    answer: tuple[str, ...],
    batch_file: str | None,
    *,
    list_templates: bool,
) -> None:
    if list_templates:
        from bim.dependencies import get_templates

        for name in sorted(get_templates()):
            console.print(name, mode="raw")
        return

    from bim.commands.create_note.create_note import CommandCreateNote

    settings = get_settings(ctx, BimSettings)
    extra_answers: dict[str, str] = {}
    for a in answer:
        if "=" in a:
            k, v = a.split("=", 1)
            extra_answers[k] = v
    try:
        cmd = CommandCreateNote(
            path_zettelkasten=Path(settings.path_zettelkasten).expanduser().resolve(),
            zettel_type=zettel_type,
            title=title,
            tags=tags,
            extra_answers=extra_answers,
            batch_file=Path(batch_file) if batch_file else None,
        )
        cmd.execute()
    except (FileNotFoundError, ValueError) as exc:
        console.panic(str(exc))


@cli.command("query", help="Query zettels with YAML filter/sort/output spec")
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.option("-e", "--edit", is_flag=True, default=False, help="Pick result with fzf and open in nvim")
@click.option("--tui", is_flag=True, default=False, help="Render output in interactive TUI")
@click.option("-l", "--list", "list_queries", is_flag=True, default=False, help="List available queries")
@click.pass_context
def query(
    ctx: click.Context,
    query_file: str | None,
    query_string: str | None,
    *,
    edit: bool,
    tui: bool,
    list_queries: bool,
) -> None:
    if list_queries:
        from bim.commands.query.query import BUNDLED_QUERY_DIR
        from bim.dependencies import list_query_files

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
        tui=tui,
    )
    cmd.execute()


@cli.command("edit", help="Edit zettel metadata")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.option("--title", default=None, help="New title")
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option("--type", "zettel_type", default=None, help="Note type")
@click.option("--processed/--no-processed", default=None, help="Processed flag")
@click.option("--publish/--no-publish", default=None, help="Publish flag")
@click.option("-s", "--set", "extra_sets", multiple=True, help="Arbitrary key=value metadata")
@click.pass_context
def edit_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    title: str | None,
    tags: str | None,
    zettel_type: str | None,
    processed: bool | None,
    publish: bool | None,
    extra_sets: tuple[str, ...],
) -> None:
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

    resolved = _resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    if not changes and len(resolved) > 1:
        console.failure("TUI edit requires a single path")
        return

    from bim.commands.edit_note.edit_note import CommandEditNote

    cmd = CommandEditNote(paths=resolved, changes=changes or None)
    cmd.execute()


@cli.command("archive", help="Archive zettel(s): set processed + move to archive dir")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.option("--undo", is_flag=True, default=False, help="Unarchive (move back to zettelkasten)")
@click.pass_context
def archive_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    *,
    undo: bool,
) -> None:
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.archive_note.archive_note import CommandArchiveNote

    settings = get_settings(ctx, BimSettings)
    cmd = CommandArchiveNote(
        paths=resolved,
        path_archive=Path(settings.path_archive).expanduser().resolve(),
        path_zettelkasten=Path(settings.path_zettelkasten).expanduser().resolve(),
        undo=undo,
    )
    cmd.execute()


@cli.command("show", help="Display zettel content")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.pass_context
def show_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
) -> None:
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.show_note.show_note import CommandShowNote

    cmd = CommandShowNote(paths=resolved)
    cmd.execute()


@cli.command("delete", help="Permanently delete zettel(s)")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation")
@click.pass_context
def delete_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    *,
    force: bool,
) -> None:
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.delete_note.delete_note import CommandDeleteNote

    batch = query_file is not None or query_string is not None
    cmd = CommandDeleteNote(paths=resolved, force=force, batch=batch)
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
