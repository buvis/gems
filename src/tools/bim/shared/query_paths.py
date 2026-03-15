from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import get_settings
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase

from bim.commands.query.query import BUNDLED_QUERY_DIR
from bim.dependencies import get_evaluator, get_repo, parse_query_file, parse_query_string, resolve_query_file
from bim.settings import BimSettings


def resolve_paths(
    ctx: click.Context,
    paths: tuple[str, ...],
    query_file: str | None,
    query_string: str | None,
) -> list[Path] | None:
    """Resolve paths from explicit args or query flags. Returns None on error."""
    has_paths = len(paths) > 0
    has_query = query_file is not None or query_string is not None

    if has_paths and has_query:
        console.failure("Provide paths or -Q/-q, not both")
        return None

    if has_query:
        settings = get_settings(ctx, BimSettings)
        default_dir = str(Path(settings.path_zettelkasten).expanduser().resolve())
        return resolve_query_paths(query_file, query_string, default_dir)

    if has_paths:
        return [Path(p) for p in paths]

    console.failure("Provide paths or -Q/-q")
    return None


def resolve_query_paths(
    query_file: str | None,
    query_string: str | None,
    default_directory: str,
) -> list[Path] | None:
    """Run a query and return file paths from results. None on error."""
    if query_file:
        resolved = resolve_query_file(query_file, bundled_dir=BUNDLED_QUERY_DIR)
        spec = parse_query_file(str(resolved))
    elif query_string:
        spec = parse_query_string(query_string)
    else:
        console.failure("Provide -Q/--query-file or -q/--query")
        return None

    if spec.source.directory is None:
        spec.source.directory = default_directory

    repo = get_repo(extensions=spec.source.extensions)
    rows = QueryZettelsUseCase(repo, get_evaluator()).execute(spec)

    if not rows:
        console.warning("Query returned no results")
        return None

    paths = []
    for row in rows:
        fp = row.get("file_path")
        if fp:
            paths.append(Path(fp))

    if not paths:
        console.failure("Query results have no file_path column")
        return None

    return paths
