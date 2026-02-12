from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from buvis.pybase.adapters import console
from buvis.pybase.zettel import MarkdownZettelRepository
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    _default_cache_path,
)
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval
from buvis.pybase.zettel.infrastructure.query.output_formatter import (
    format_csv,
    format_markdown,
    format_table,
)
from buvis.pybase.zettel.infrastructure.query.query_spec_parser import (
    parse_query_file,
    parse_query_string,
)


class CommandQuery:
    def __init__(
        self,
        default_directory: str,
        file: str | None = None,
        query: str | None = None,
    ) -> None:
        self.default_directory = default_directory
        self.file = file
        self.query = query

    def execute(self) -> None:
        if self.file:
            spec = parse_query_file(self.file)
        elif self.query:
            spec = parse_query_string(self.query)
        else:
            console.failure("Provide -f/--file or -q/--query")
            return

        if spec.source.directory is None:
            spec.source.directory = self.default_directory

        directory = str(Path(spec.source.directory).expanduser().resolve())

        # Start background cache refresh immediately (walks full dir tree)
        refresh_proc = _start_cache_refresh(directory)

        repo = MarkdownZettelRepository()
        use_case = QueryZettelsUseCase(repo, python_eval)

        t0 = time.perf_counter()
        rows = use_case.execute(spec)
        elapsed = time.perf_counter() - t0

        if not rows:
            console.warning("No results")
            _finish_refresh(refresh_proc, None, use_case, spec)
            return

        columns = list(rows[0].keys())
        output = spec.output

        if output.format == "table":
            format_table(rows, columns)
        elif output.format == "csv":
            text = format_csv(rows, columns)
            _write_output(text, output.file)
        elif output.format == "markdown":
            text = format_markdown(rows, columns)
            _write_output(text, output.file)
        else:
            console.failure(f"Unknown output format: {output.format}")

        console.info(f"{len(rows)} rows, query took {elapsed:.2f}s")

        _finish_refresh(refresh_proc, rows, use_case, spec)


def _start_cache_refresh(directory: str) -> subprocess.Popen[bytes] | None:
    """Start a subprocess that walks the directory and updates the cache."""
    try:
        from buvis.pybase.zettel._core import refresh_cache as _rc  # noqa: F401
    except ImportError:
        return None

    cache_path = _default_cache_path()
    script = (
        "from buvis.pybase.zettel._core import refresh_cache;"
        f"print(refresh_cache({directory!r}, {cache_path!r}))"
    )
    return subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )


def _finish_refresh(
    proc: subprocess.Popen[bytes] | None,
    original_rows: list[dict[str, Any]] | None,
    use_case: QueryZettelsUseCase,
    spec: Any,
) -> None:
    """Wait for background refresh, then verify results."""
    if proc is None:
        return

    with console.status("Checking for updates..."):
        stdout, _ = proc.communicate()
        summary = stdout.decode().strip()

        if not summary:
            stale = False
        else:
            new_rows = use_case.execute(spec)
            if original_rows is None:
                stale = bool(new_rows)
            else:
                stale = not _results_match(original_rows, new_rows)

    if stale:
        console.warning("Updates found — re-run for latest results")
    else:
        console.success("Up to date")


def _results_match(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False
    try:
        fa = {tuple(sorted(r.items())) for r in a}
        fb = {tuple(sorted(r.items())) for r in b}
        return fa == fb
    except TypeError:
        # unhashable values — fall back to length comparison
        return len(a) == len(b)


def _write_output(text: str, file: str | None) -> None:
    if file:
        Path(file).write_text(text, encoding="utf-8")
        console.success(f"Written to {file}")
    else:
        console.print(text, mode="raw")
