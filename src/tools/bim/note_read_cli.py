from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import apply_generated_options, get_settings

from bim.params.format_note import FormatNoteParams
from bim.params.query import QueryParams
from bim.settings import BimSettings
from bim.shared.query_paths import resolve_paths

__all__ = ["register_note_read_commands"]


def register_note_read_commands(cli: click.Group) -> None:
    cli.add_command(format_note)
    cli.add_command(sync_note)
    cli.add_command(show_note)
    cli.add_command(query)


@click.command("format", help="Format a note")
@click.argument("paths", nargs=-1, required=False)
@click.option("-Q", "--query-file", "query_file", default=None, help="Query name or path to YAML spec")
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
    /,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
    output: Path | None,
    **kwargs: Any,
) -> None:
    resolved = resolve_paths(ctx, paths, query_file, query_string)
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
        console.failure(result.error or "Format failed")
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


@click.command("sync", help="Synchronize note(s) with external system")
@click.argument("paths", nargs=-1, required=False)
@click.option("-t", "--target", "target_system", required=True, help="Target system (e.g. jira)")
@click.option("-Q", "--query-file", "query_file", default=None, help="Query name or path to YAML spec")
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
    resolved = resolve_paths(ctx, paths, query_file, query_string)
    if resolved is None:
        return

    from bim.commands.sync_note.sync_note import CommandSyncNote
    from bim.dependencies import get_formatter, get_repo
    from bim.params.sync_note import SyncNoteParams

    if len(resolved) > 1 and not force:
        if not console.confirm(f"Sync {len(resolved)} zettels to {target_system}?"):
            return

    bim_settings = get_settings(ctx, BimSettings)
    jira_adapter: dict[str, Any] = bim_settings.adapters.get("jira", {})
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
            console.failure(result.error or "Sync failed")
    except (ValueError, FileNotFoundError) as exc:
        console.panic(str(exc))
        return
    except NotImplementedError:
        console.panic(f"Sync target '{target_system}' not supported")
        return


@click.command("query", help="Query zettels with YAML filter/sort/output spec")
@click.option("-Q", "--query-file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@apply_generated_options(QueryParams)
@click.option("-l", "--list", "list_queries", is_flag=True, default=False, help="List available queries")
@click.pass_context
def query(
    ctx: click.Context,
    /,
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
        console.failure("Provide -Q/--query-file or -q/--query")
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


@click.command("show", help="Display zettel content")
@click.argument("paths", nargs=-1, required=False)
@click.option("-Q", "--query-file", "query_file", default=None, help="Query name or path to YAML spec")
@click.option("-q", "--query", "query_string", default=None, help="Inline YAML query string")
@click.pass_context
def show_note(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
) -> None:
    resolved = resolve_paths(ctx, paths, query_file, query_string)
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
        console.failure(result.error or "Show failed")
