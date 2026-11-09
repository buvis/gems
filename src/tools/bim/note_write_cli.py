from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import apply_generated_options, get_settings

from bim.params.archive_note import ArchiveNoteParams
from bim.params.delete_note import DeleteNoteParams
from bim.params.edit_note import EditNoteParams
from bim.settings import BimSettings
from bim.shared.query_paths import resolve_paths

if TYPE_CHECKING:
    from bim.params.create_note import CreateNoteParams

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
        ctx.exit(1)
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
@click.option(
    "--summary-file", default=None, help="article only: Markdown file with the core facts; the body is archived"
)
@click.option("--dry-run", is_flag=True, default=False, help="Render the note without writing anything")
@click.option("--json", "as_json", is_flag=True, default=False, help="Print the result as one JSON object")
@click.option(
    "--no-daily-log",
    "daily_log",
    is_flag=True,
    flag_value=False,
    default=True,
    help="Do not log the new note in today's daily note",
)
@click.option(
    "--no-link-contacts",
    "link_contacts",
    is_flag=True,
    flag_value=False,
    default=True,
    help="Keep the body verbatim: do not wikilink known contacts",
)
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
    summary_file: str | None,
    dry_run: bool,
    as_json: bool,
    daily_log: bool,
    link_contacts: bool,
    list_templates: bool,
) -> None:
    if list_templates:
        if as_json:
            _fail_json(ctx, "--list cannot be combined with --json")
        from bim.dependencies import get_templates

        for name in sorted(get_templates()):
            console.print(name, mode="raw")
        return

    settings = get_settings(ctx, BimSettings)
    from bim.params.create_note import CreateNoteParams

    extra_answers = dict(a.split("=", 1) for a in answer if "=" in a)
    params = CreateNoteParams(
        zettel_type=zettel_type,
        title=title,
        tags=tags,
        extra_answers=extra_answers,
        source=Path(source).expanduser() if source is not None else None,
        dry_run=dry_run,
        daily_log=daily_log,
        link_contacts=link_contacts,
    )
    _dispatch_create(settings, ctx, params, body_file, summary_file, as_json=as_json)


def _dispatch_create(
    settings: BimSettings,
    ctx: click.Context,
    params: CreateNoteParams,
    body_file: str | None,
    summary_file: str | None,
    *,
    as_json: bool,
) -> None:
    path_zettelkasten = Path(settings.path_zettelkasten).expanduser().resolve()
    path_projects = Path(settings.path_projects).expanduser()
    path_daily = Path(settings.path_daily).expanduser()
    path_articles = Path(settings.path_articles).expanduser()
    if any(
        (
            as_json,
            params.dry_run,
            body_file is not None,
            params.source is not None,
            summary_file is not None,
            not params.daily_log,
            not params.link_contacts,
            params.zettel_type and params.title,
        )
    ):
        _create_note_scripted(
            ctx,
            path_zettelkasten,
            path_projects=path_projects,
            path_daily=path_daily,
            path_articles=path_articles,
            params=params,
            body_file=body_file,
            summary_file=summary_file,
            as_json=as_json,
        )
        return
    _create_note_interactive(path_zettelkasten, path_projects, path_daily, path_articles, params)


def _create_note_interactive(
    path_zettelkasten: Path,
    path_projects: Path,
    path_daily: Path,
    path_articles: Path,
    params: CreateNoteParams,
) -> None:
    from bim.tui.create_note import CreateNoteApp

    app = CreateNoteApp(
        path_zettelkasten=path_zettelkasten,
        preselected_type=params.zettel_type,
        preselected_title=params.title,
        preselected_tags=params.tags,
        extra_answers=params.extra_answers,
        path_projects=path_projects,
        path_daily=path_daily,
        path_articles=path_articles,
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
    path_daily: Path,
    path_articles: Path,
    params: CreateNoteParams,
    body_file: str | None,
    summary_file: str | None,
    as_json: bool,
) -> None:
    from bim.commands.create_note.create_note import CommandCreateNote
    from bim.dependencies import get_formatter, get_hook_runner, get_repo, get_templates

    def fail(message: str) -> None:
        if as_json:
            _fail_json(ctx, message)
        console.panic(message)

    if body_file is not None and params.source is not None:
        fail("--body-file and --source are mutually exclusive")
        return
    if summary_file is not None and params.zettel_type != "article":
        fail("--summary-file is only for the article template")
        return
    try:
        params.body = _read_create_input(body_file, stdin=True)
        params.summary = _read_create_input(summary_file)
        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=path_zettelkasten,
            repo=get_repo(),
            templates=get_templates(),
            hook_runner=get_hook_runner(path_projects),
            formatter=get_formatter(),
            path_daily=path_daily,
            path_articles=path_articles,
        )
    except (OSError, UnicodeError) as exc:
        fail(str(exc))
        return
    _render_create_result(ctx, cmd.execute(), as_json=as_json)


def _read_create_input(path: str | None, *, stdin: bool = False) -> str | None:
    if stdin and path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8") if path is not None else None


def _render_create_result(ctx: click.Context, result: Any, *, as_json: bool) -> None:
    if as_json:
        if not result.success:
            _fail_json(ctx, result.error or "Create failed")
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
            ctx.exit(1)
            return
        path = resolved[0]
        if not path.is_file():
            console.failure(f"{path} doesn't exist")
            ctx.exit(1)
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
