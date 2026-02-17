from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import (
    GlobalSettings,
    apply_generated_options,
    buvis_options,
    get_settings,
)

from bim.params.archive_note import ArchiveNoteParams
from bim.params.delete_note import DeleteNoteParams
from bim.params.edit_note import EditNoteParams
from bim.params.format_note import FormatNoteParams
from bim.params.query import QueryParams
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
        from bim.shared.query_paths import resolve_query_paths

        settings = get_settings(ctx, BimSettings)
        default_dir = str(Path(settings.path_zettelkasten).expanduser().resolve())
        return resolve_query_paths(query_file, query_string, default_dir)

    if has_paths:
        return [Path(p) for p in paths]

    console.failure("Provide paths or -f/-q")
    return None


def _resolve_output_path(
    note: Any,
    path_output: Path,
    path_note: Path,
    path_zettelkasten: Path,
) -> Path:
    overwrite_confirmed = False

    while path_output.is_file() and not overwrite_confirmed:
        console.failure(f"{path_output} already exists")
        console.nl()
        console.print(path_output.read_text(encoding="utf-8"), mode="raw")
        console.nl()
        overwrite_file = console.confirm("Overwrite file?")

        if overwrite_file:
            overwrite_confirmed = True
        else:
            alternative_note_id = (note.id or 0) + 1
            alternative_path_output = path_zettelkasten / f"{alternative_note_id}.md"

            while alternative_path_output.is_file():
                alternative_note_id += 1
                alternative_path_output = path_zettelkasten / f"{alternative_note_id}.md"

            accept_alternative_id = console.confirm(
                f"Change ID to {alternative_note_id}?",
            )

            if accept_alternative_id:
                path_output = alternative_path_output
                note.data.metadata["id"] = alternative_note_id
            else:
                console.panic(f"Can't import {path_note}")

    return path_output


def _interactive_import(path_note: Path, path_zettelkasten: Path) -> None:
    if not path_note.is_file():
        console.failure(f"{path_note} doesn't exist")
        return

    from buvis.pybase.formatting import StringOperator
    from buvis.pybase.zettel import ReadZettelUseCase
    from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

    from bim.dependencies import get_formatter, get_repo

    original_content = path_note.read_text(encoding="utf-8")
    repo = get_repo()
    reader = ReadZettelUseCase(repo)
    note = reader.execute(str(path_note))

    if note.type == "project":
        note.data.metadata["resources"] = f"[project resources]({path_note.parent.resolve().as_uri()})"

    if note.id is None:
        console.failure(f"Note at {path_note} has no ID, skipping")
        return

    path_output = path_zettelkasten / f"{note.id}.md"
    formatted_content = PrintZettelUseCase(get_formatter()).execute(note.get_data())
    _, _, markdown_content = formatted_content.partition("\n---\n")

    console.print_side_by_side(
        "Original",
        original_content,
        "Formatted",
        formatted_content,
        mode_left="raw",
        mode_right="raw",
    )
    console.nl()

    is_import_approved = console.confirm(
        "Check the resulting note and compare to original. Should I continue importing?"
    )

    if not is_import_approved:
        console.warning("Import cancelled by user")
        return

    path_output = _resolve_output_path(note, path_output, path_note, path_zettelkasten)

    if not note.tags:
        console.nl()
        console.warning("There are no tags in this note. I will suggest some.")
        console.nl()
        new_tags = []
        for suggested_tag in StringOperator.suggest_tags(markdown_content):
            add_tag = console.confirm(f"Tag with '{suggested_tag}'?")
            if add_tag:
                new_tags.append(suggested_tag)
        note.tags = new_tags
        formatted_content = PrintZettelUseCase(get_formatter()).execute(note.get_data())

    path_output.write_text(formatted_content, encoding="utf-8")
    console.success(f"Note imported as {path_output}")
    remove_file = console.confirm("Do you want to remove the original?")

    if remove_file:
        path_note.unlink()
        console.success(f"{path_note} was removed")


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
    settings = get_settings(ctx, BimSettings)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    scripted = tags is not None or force or remove_original

    if not scripted and len(paths) > 1:
        console.failure("interactive import requires a single path")
        return

    path_zettelkasten = Path(settings.path_zettelkasten).expanduser().resolve()

    if not scripted:
        _interactive_import(Path(paths[0]), path_zettelkasten)
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
    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error)


@cli.command("format", help="Format a note")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(FormatNoteParams)
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
    output: None | Path,
    **kwargs: Any,
) -> None:
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.format_note.format_note import CommandFormatNote
    from bim.dependencies import get_formatter, get_repo

    params = FormatNoteParams(paths=resolved, path_output=Path(output) if output else None, **kwargs)
    cmd = CommandFormatNote(
        params=params,
        repo=get_repo(),
        formatter=get_formatter(),
    )
    result = cmd.execute()
    for w in result.warnings:
        console.warning(w)
    if not result.success:
        console.failure(result.error)
        return
    if result.metadata.get("written_to"):
        console.success(f"Formatted note written to {result.metadata['written_to']}")
    elif result.output:
        original = result.metadata.get("original")
        if params.diff and original and original != result.output:
            console.print_side_by_side(
                "Original",
                original,
                "Formatted",
                result.output,
                mode_left="raw",
                mode_right="markdown_with_frontmatter",
            )
        elif params.highlight:
            console.print(result.output, mode="markdown_with_frontmatter")
        else:
            console.print(result.output, mode="raw")
    elif result.metadata.get("formatted_count"):
        console.success(f"Formatted {result.metadata['formatted_count']} files")


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
    from bim.dependencies import get_formatter, get_repo
    from bim.params.sync_note import SyncNoteParams

    if len(resolved) > 1 and not force:
        if not console.confirm(f"Sync {len(resolved)} zettels to {target_system}?"):
            return

    global_settings = get_settings(ctx, GlobalSettings)
    jira_adapter: dict[str, Any] = (global_settings.model_extra or {}).get("jira_adapter", {})
    try:
        params = SyncNoteParams(paths=resolved, target_system=target_system)
        cmd = CommandSyncNote(
            params=params,
            jira_adapter_config=jira_adapter,
            repo=get_repo(),
            formatter=get_formatter(),
        )
        result = cmd.execute()
        for w in result.warnings:
            console.warning(w)
        if result.success:
            if result.output:
                console.success(result.output)
        else:
            console.failure(result.error)
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
        result = cmd.execute()
        if not result.success:
            console.failure(result.error)
            return
        if result.output:
            console.print(result.output, mode="raw")
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
    if zettel_type and title:
        from bim.commands.create_note.create_note import CommandCreateNote
        from bim.dependencies import get_hook_runner, get_repo, get_templates
        from bim.params.create_note import CreateNoteParams

        try:
            params = CreateNoteParams(
                zettel_type=zettel_type,
                title=title,
                tags=tags,
                extra_answers=extra_answers,
            )
            cmd = CommandCreateNote(
                params=params,
                path_zettelkasten=path_zettelkasten,
                repo=get_repo(),
                templates=get_templates(),
                hook_runner=get_hook_runner(),
            )
        except FileNotFoundError as exc:
            console.panic(str(exc))
            return
        result = cmd.execute()
        for w in result.warnings:
            console.warning(w)
        if result.success:
            console.success(result.output)
        else:
            console.failure(result.error)
        return

    from bim.tui.create_note import CreateNoteApp

    app = CreateNoteApp(
        path_zettelkasten=path_zettelkasten,
        preselected_type=zettel_type,
        preselected_title=title,
        preselected_tags=tags,
        extra_answers=extra_answers,
    )
    app.run()


@cli.command("query", help="Query zettels with YAML filter/sort/output spec")
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(QueryParams)
@click.option("-l", "--list", "list_queries", is_flag=True, default=False, help="List available queries")
@click.pass_context
def query(
    ctx: click.Context,
    query_file: str | None,
    query_string: str | None,
    list_queries: bool,
    **kwargs: Any,
) -> None:
    if list_queries:
        from bim.commands.query.query import BUNDLED_QUERY_DIR
        from bim.dependencies import list_query_files

        for name, path in sorted(list_query_files(bundled_dir=BUNDLED_QUERY_DIR).items()):
            console.print(f"{name:30s} {path}", mode="raw")
        return

    from bim.commands.query.query import BUNDLED_QUERY_DIR, CommandQuery
    from bim.dependencies import (
        get_evaluator,
        get_repo,
        parse_query_file,
        parse_query_string,
        resolve_query_file,
    )
    from bim.shared.query_presentation import present_query_result
    settings = get_settings(ctx, BimSettings)
    if query_file:
        resolved = resolve_query_file(query_file, bundled_dir=BUNDLED_QUERY_DIR)
        spec = parse_query_file(str(resolved))
    elif query_string:
        spec = parse_query_string(query_string)
    else:
        console.failure("Provide -f/--file or -q/--query")
        return

    default_directory = str(Path(settings.path_zettelkasten).expanduser().resolve())
    archive_directory = str(Path(settings.path_archive).expanduser().resolve())
    repo = get_repo(extensions=spec.source.extensions)
    evaluator = get_evaluator()

    params = QueryParams(spec=spec, default_directory=default_directory, **kwargs)
    cmd = CommandQuery(
        params=params,
        repo=repo,
        evaluator=evaluator,
    )
    t0 = time.perf_counter()
    result = cmd.execute()
    elapsed = time.perf_counter() - t0

    rows = result.metadata["rows"]
    columns = result.metadata["columns"]
    directory = result.metadata["directory"]
    spec = result.metadata["spec"]

    if not rows:
        console.warning("No results")
        return

    present_query_result(
        rows,
        columns,
        spec,
        tui=params.tui,
        edit=params.edit,
        archive_directory=archive_directory,
        directory=directory,
        repo=repo,
        evaluator=evaluator,
    )
    console.info(f"{len(rows)} rows, query took {elapsed:.2f}s")


@cli.command("edit", help="Edit zettel metadata")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(EditNoteParams)
@click.option("-s", "--set", "extra_sets", multiple=True, help="Arbitrary key=value metadata")
@click.pass_context
def edit_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    extra_sets: tuple[str, ...],
    **kwargs: Any,
) -> None:
    changes: dict[str, Any] = {}
    title = kwargs.get("title")
    if title is not None:
        changes["title"] = title
    tags = kwargs.get("tags")
    if tags is not None:
        changes["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    zettel_type = kwargs.get("zettel_type")
    if zettel_type is not None:
        changes["type"] = zettel_type
    processed = kwargs.get("processed")
    if processed is not None:
        changes["processed"] = processed
    publish = kwargs.get("publish")
    if publish is not None:
        changes["publish"] = publish
    for s in extra_sets:
        if "=" in s:
            k, v = s.split("=", 1)
            changes[k] = v

    resolved = _resolve_paths(ctx, paths, query_file, query_string)
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
    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error)


@cli.command("archive", help="Archive zettel(s): set processed + move to archive dir")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
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
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
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
    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error)


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
    from bim.dependencies import get_formatter, get_repo
    from bim.params.show_note import ShowNoteParams

    params = ShowNoteParams(paths=resolved)
    cmd = CommandShowNote(params=params, repo=get_repo(), formatter=get_formatter())
    result = cmd.execute()
    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.print(result.output, mode="raw")
    else:
        console.failure(result.error)


@cli.command("delete", help="Permanently delete zettel(s)")
@click.argument("paths", nargs=-1, required=False)
@click.option("-f", "--file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(DeleteNoteParams)
@click.pass_context
def delete_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    **kwargs: Any,
) -> None:
    resolved = _resolve_paths(ctx, paths, query_file, query_string)
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
    for w in result.warnings:
        console.warning(w)
    if result.success:
        count = result.metadata.get("deleted_count", 0)
        if count:
            console.success(f"Deleted {count} zettel(s)")
    else:
        console.failure(result.error)


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
    from bim.params.serve import ServeParams

    settings = get_settings(ctx, BimSettings)
    params = ServeParams(
        default_directory=str(Path(settings.path_zettelkasten).expanduser().resolve()),
        archive_directory=str(Path(settings.path_archive).expanduser().resolve()),
        host=host,
        port=port,
        no_browser=no_browser,
    )
    cmd = CommandServe(params=params)
    cmd.execute()


if __name__ == "__main__":
    cli()
