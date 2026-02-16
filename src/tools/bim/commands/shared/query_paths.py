from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase

from bim.commands.query.query import BUNDLED_QUERY_DIR
from bim.dependencies import get_evaluator, get_repo, parse_query_file, parse_query_string, resolve_query_file


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
        console.failure("Provide -f/--file or -q/--query")
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
