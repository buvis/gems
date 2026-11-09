from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import apply_generated_options, get_settings

from bim.params.archive_note import ArchiveNoteParams
from bim.params.delete_note import DeleteNoteParams
from bim.params.edit_note import EditNoteParams
from bim.settings import BimSettings
from bim.shared.query_paths import resolve_paths

__all__ = ["register_note_write_commands"]


def register_note_write_commands(cli: click.Group) -> None:
    cli.add_command(import_note)
    cli.add_command(create_note)
    cli.add_command(edit_note)
    cli.add_command(archive_note)
    cli.add_command(delete_note)


@click.command("import", help="Import a note to zettelkasten")
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
    settings = get_settings(ctx, BimSettings)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    scripted = tags is not None or force or remove_original

    if not scripted and len(paths) > 1:
        console.failure("interactive import requires a single path")
        return

    path_zettelkasten = Path(settings.path_zettelkasten).expanduser().resolve()

    if not scripted:
        bim_settings = get_settings(ctx, BimSettings)
        from bim.shared.import_helpers import interactive_import

        interactive_import(Path(paths[0]), path_zettelkasten, bim_settings)
        return

    from bim.commands.import_note.import_note import CommandImportNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.import_note import ImportNoteParams

    params = ImportNoteParams(
        paths=[Path(p) for p in paths],
        tags=tag_list,
        force=force,
        remove_original=remove_original,
    )
    cmd = CommandImportNote(
        params=params,
        path_zettelkasten=path_zettelkasten,
        repo=get_repo(),
        formatter=get_formatter(),
    )
    result = cmd.execute()
    console.report_result(result, failure_msg="Import failed")
    if not result.success:
        ctx.exit(1)


@click.command("create", help="Create a new zettel from template")
@click.option("-t", "--type", "zettel_type", default=None, help="Template type (note, project)")
@click.option("--title", default=None, help="Zettel title")
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option("-a", "--answer", multiple=True, help="Template question answer as key=value")
@click.option("--body-file", default=None, help="Markdown file with the note body, or - for stdin")
@click.option(
    "--source", default=None, help="Inbox Markdown file to convert; moved to .trash/ after the note is written"
)
@click.option("--dry-run", is_flag=True, default=False, help="Render the note without writing anything")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the result as one JSON object")
@click.option("-l", "--list", "list_templates", is_flag=True, default=False, help="List available templates")
@click.pass_context
def create_note(
    ctx: click.Context,
    *,
    zettel_type: str | None,
    title: str | None,
    tags: str | None,
    answer: tuple[str, ...],
    body_file: str | None,
    source: str | None,
    dry_run: bool,
    as_json: bool,
    list_templates: bool,
) -> None:
    scripted = as_json or dry_run or body_file is not None or source is not None
    if list_templates:
        if as_json:
            _fail_json(ctx, "--list cannot be combined with --json")
        from bim.dependencies import get_templates

        for name in sorted(get_templates()):
            console.print(name, mode="raw")
        return

    settings = get_settings(ctx, BimSettings)
    extra_answers: dict[str, str] = {}
    for a in answer:
        if "=" in a:
            k, v = a.split("=", 1)
            extra_answers[k] = v
    path_zettelkasten = Path(settings.path_zettelkasten).expanduser().resolve()
    path_projects = Path(settings.path_projects).expanduser()
    if scripted or (zettel_type and title):
        _create_note_scripted(
            ctx,
            path_zettelkasten,
            path_projects=path_projects,
            zettel_type=zettel_type,
            title=title,
            tags=tags,
            extra_answers=extra_answers,
            body_file=body_file,
            source=source,
            dry_run=dry_run,
            as_json=as_json,
        )
        return

    from bim.tui.create_note import CreateNoteApp

    app = CreateNoteApp(
        path_zettelkasten=path_zettelkasten,
        preselected_type=zettel_type,
        preselected_title=title,
        preselected_tags=tags,
        extra_answers=extra_answers,
        path_projects=path_projects,
    )
    app.run()


def _fail_json(ctx: click.Context, message: str) -> None:
    # Scripting contract v1 (PRD 00118): the JSON payload is the one sanctioned
    # bypass of the console adapter, because Rich would wrap a long line.
    click.echo(json.dumps({"error": message}, ensure_ascii=False))
    ctx.exit(1)


def _create_note_scripted(
    ctx: click.Context,
    path_zettelkasten: Path,
    *,
    path_projects: Path,
    zettel_type: str | None,
    title: str | None,
    tags: str | None,
    extra_answers: dict[str, str],
    body_file: str | None,
    source: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    from bim.commands.create_note.create_note import CommandCreateNote
    from bim.dependencies import get_formatter, get_hook_runner, get_repo, get_templates
    from bim.params.create_note import CreateNoteParams

    def fail(message: str) -> None:
        if as_json:
            _fail_json(ctx, message)
        console.panic(message)

    if body_file is not None and source is not None:
        fail("--body-file and --source are mutually exclusive")
        return
    try:
        body = None
        if body_file == "-":
            body = sys.stdin.read()
        elif body_file is not None:
            body = Path(body_file).expanduser().read_text(encoding="utf-8")
        params = CreateNoteParams(
            zettel_type=zettel_type,
            title=title,
            tags=tags,
            extra_answers=extra_answers,
            body=body,
            source=Path(source).expanduser() if source is not None else None,
            dry_run=dry_run,
        )
        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=path_zettelkasten,
            repo=get_repo(),
            templates=get_templates(),
            hook_runner=get_hook_runner(path_projects),
            formatter=get_formatter(),
        )
    except (OSError, UnicodeError) as exc:
        fail(str(exc))
        return
    result = cmd.execute()
    if as_json:
        if not result.success:
            fail(result.error or "Create failed")
            return
        payload = {**result.metadata, "warnings": result.warnings} if result.warnings else result.metadata
        click.echo(json.dumps(payload, ensure_ascii=False))
        return

    def report_success(r: Any) -> None:
        if r.metadata.get("dry_run"):
            console.print(r.metadata["content"], mode="raw")
        else:
            console.success(r.output or "Created")

    console.report_result(result, on_success=report_success, failure_msg="Create failed")
    if not result.success:
        ctx.exit(1)


@click.command("edit", help="Edit zettel metadata")
@click.argument("paths", nargs=-1, required=False)
@click.option("-Q", "--query-file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(EditNoteParams)
@click.option("-s", "--set", "extra_sets", multiple=True, help="Arbitrary key=value metadata")
@click.pass_context
def edit_note(
    ctx: click.Context,
    /,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    extra_sets: tuple[str, ...],
    **kwargs: Any,
) -> None:
    from bim.shared.edit_helpers import build_edit_changes

    changes = build_edit_changes(kwargs, extra_sets)

    resolved = resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    if not changes:
        if len(resolved) > 1:
            console.failure("TUI edit requires a single path")
            return
        path = resolved[0]
        if not path.is_file():
            console.failure(f"{path} doesn't exist")
            return
        from bim.tui.edit_note import EditNoteApp

        app = EditNoteApp(path=path)
        app.run()
        return

    from bim.commands.edit_note.edit_note import CommandEditNote
    from bim.dependencies import get_repo

    params = EditNoteParams(paths=resolved, changes=changes, **kwargs)
    cmd = CommandEditNote(params=params, repo=get_repo())
    result = cmd.execute()
    console.report_result(result, failure_msg="Edit failed")
    if not result.success:
        ctx.exit(1)


@click.command("archive", help="Archive zettel(s): set processed + move to archive dir")
@click.argument("paths", nargs=-1, required=False)
@click.option("-Q", "--query-file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(ArchiveNoteParams)
@click.pass_context
def archive_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    *,
    undo: bool,
) -> None:
    resolved = resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.archive_note.archive_note import CommandArchiveNote
    from bim.dependencies import get_repo

    settings = get_settings(ctx, BimSettings)
    params = ArchiveNoteParams(paths=resolved, undo=undo)
    cmd = CommandArchiveNote(
        params=params,
        path_archive=Path(settings.path_archive).expanduser().resolve(),
        path_zettelkasten=Path(settings.path_zettelkasten).expanduser().resolve(),
        repo=get_repo(),
    )
    result = cmd.execute()
    console.report_result(result, failure_msg="Archive failed")
    if not result.success:
        ctx.exit(1)


@click.command("delete", help="Permanently delete zettel(s)")
@click.argument("paths", nargs=-1, required=False)
@click.option("-Q", "--query-file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(DeleteNoteParams)
@click.pass_context
def delete_note(
    ctx: click.Context,
    /,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    **kwargs: Any,
) -> None:
    resolved = resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.delete_note.delete_note import CommandDeleteNote
    from bim.dependencies import get_repo

    params = DeleteNoteParams(paths=resolved, **kwargs)
    batch = query_file is not None or query_string is not None
    if batch and not params.force:
        if not console.confirm(f"Permanently delete {len(resolved)} zettels?"):
            return
        confirmed_paths = resolved
    elif not params.force and not batch:
        confirmed_paths = [path for path in resolved if console.confirm(f"Permanently delete {path.name}?")]
    else:
        confirmed_paths = resolved

    params = DeleteNoteParams(paths=confirmed_paths, **kwargs)
    cmd = CommandDeleteNote(params=params, repo=get_repo())
    result = cmd.execute()
    console.report_result(
        result,
        on_success=lambda r: (
            console.success(f"Deleted {r.metadata.get('deleted_count', 0)} zettel(s)")
            if r.metadata.get("deleted_count")
            else None
        ),
        failure_msg="Delete failed",
    )
    if not result.success:
        ctx.exit(1)
