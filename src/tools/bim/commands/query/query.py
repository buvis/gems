from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase

from bim.commands.shared.os_open import open_in_os
from bim.dependencies import (
    format_query_csv,
    format_query_html,
    format_query_json,
    format_query_jsonl,
    format_query_kanban,
    format_query_markdown,
    format_query_pdf,
    format_query_table,
    get_cache_path,
    get_evaluator,
    get_repo,
    parse_query_file,
    parse_query_string,
    resolve_query_file,
)

from rich.text import Text

BUNDLED_QUERY_DIR = Path(__file__).parent


class CommandQuery:
    def __init__(
        self,
        default_directory: str,
        archive_directory: str | None = None,
        file: str | None = None,
        query: str | None = None,
        *,
        edit: bool = False,
        tui: bool = False,
    ) -> None:
        self.default_directory = default_directory
        self.archive_directory = archive_directory
        self.file = file
        self.query = query
        self.edit = edit
        self.tui = tui

    def execute(self) -> None:
        if self.file:
            resolved = resolve_query_file(self.file, bundled_dir=BUNDLED_QUERY_DIR)
            spec = parse_query_file(str(resolved))
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

        repo = get_repo(extensions=spec.source.extensions)
        use_case = QueryZettelsUseCase(repo, get_evaluator())

        t0 = time.perf_counter()
        rows = use_case.execute(spec)
        elapsed = time.perf_counter() - t0

        if not rows:
            console.warning("No results")
            _finish_refresh(refresh_proc, None, use_case, spec)
            return

        columns = list(rows[0].keys())
        display_columns = columns
        output = spec.output

        if self.tui:
            if output.format == "kanban":
                if not output.group_by:
                    console.failure("kanban format requires output.group_by")
                    return
                _run_kanban_tui(rows, columns, output.group_by, self.archive_directory)
            else:
                _run_tui(rows, columns, self.archive_directory)
        elif output.format == "kanban":
            if not output.group_by:
                console.failure("kanban format requires output.group_by")
                return
            display_columns = [c for c in columns if c != "file_path"]
            format_query_kanban(rows, display_columns, output.group_by)
        elif output.format == "table":
            _linkify_titles(rows)
            display_columns = [c for c in columns if c != "file_path"]
            format_query_table(rows, display_columns)
        elif output.format == "csv":
            text = format_query_csv(rows, columns)
            _write_output(text, output.file)
        elif output.format == "markdown":
            text = format_query_markdown(rows, columns)
            _write_output(text, output.file)
        elif output.format == "json":
            text = format_query_json(rows, columns)
            _write_output(text, output.file)
        elif output.format == "jsonl":
            text = format_query_jsonl(rows, columns)
            _write_output(text, output.file)
        elif output.format == "html":
            text = format_query_html(rows, columns)
            dest = output.file or _tmp_file("html")
            _write_output(text, dest)
            if not output.file:
                _open_file(dest)
        elif output.format == "pdf":
            try:
                raw = format_query_pdf(rows, columns)
            except ImportError:
                console.failure("PDF requires fpdf2: uv pip install 'buvis-gems[bim]'")
                return
            dest = output.file or _tmp_file("pdf")
            Path(dest).write_bytes(raw)
            console.success(f"Written to {dest}")
            if not output.file:
                _open_file(dest)
        else:
            console.failure(f"Unknown output format: {output.format}")

        console.info(f"{len(rows)} rows, query took {elapsed:.2f}s")

        if self.edit:
            _fzf_edit(rows, columns)

        _finish_refresh(refresh_proc, rows, use_case, spec)


def _linkify_titles(rows: list[dict[str, Any]]) -> None:
    """Turn title into a cmd-clickable file:// hyperlink when file_path exists."""
    for row in rows:
        fp = row.get("file_path")
        title = row.get("title")
        if fp and title is not None:
            t = Text(str(title))
            t.stylize(f"link {Path(fp).as_uri()}")
            row["title"] = t


def _fzf_edit(rows: list[dict[str, Any]], columns: list[str]) -> None:
    """Let user pick a row via fzf and open the file in nvim."""
    if not shutil.which("fzf"):
        console.failure("fzf not found in PATH")
        return

    # Build display lines: all columns except file_path, tab-separated
    display_cols = [c for c in columns if c != "file_path"]
    lines = []
    paths = []
    for row in rows:
        fp = str(row.get("file_path", ""))
        paths.append(fp)
        parts = [str(row.get(c, "")) for c in display_cols]
        lines.append("\t".join(parts))

    if not any(paths):
        console.failure("No file_path in results — add file_path column to use --edit")
        return

    header = "\t".join(display_cols)
    fzf_input = "\n".join(lines)

    try:
        result = subprocess.run(
            ["fzf", "--header", header, "--no-multi", "--ansi"],
            input=fzf_input,
            capture_output=True,
            text=True,
        )
    except KeyboardInterrupt:
        return

    if result.returncode != 0:
        return

    selected = result.stdout.strip()
    if not selected:
        return

    # Match selected line back to row index
    try:
        idx = lines.index(selected)
    except ValueError:
        return

    fp = paths[idx]
    if fp:
        subprocess.run(["nvim", fp])


def _start_cache_refresh(directory: str) -> subprocess.Popen[bytes] | None:
    """Start a subprocess that walks the directory and updates the cache."""
    try:
        from buvis.pybase.zettel._core import refresh_cache as _rc  # noqa: F401
    except ImportError:
        return None

    cache_path = get_cache_path()
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


def _tmp_file(ext: str) -> str:
    fd, path = tempfile.mkstemp(suffix=f".{ext}", prefix="bim_query_")
    os.close(fd)
    return path


def _open_file(path: str) -> None:
    open_in_os(path)


def _run_tui(rows: list[dict[str, Any]], columns: list[str], archive_directory: str | None = None) -> None:
    from bim.commands.query.tui import QueryTuiApp

    archive_dir = Path(archive_directory).expanduser().resolve() if archive_directory else None
    app = QueryTuiApp(rows, columns, archive_dir=archive_dir)
    app.run()


def _run_kanban_tui(
    rows: list[dict[str, Any]], columns: list[str], group_by: str, archive_directory: str | None = None,
) -> None:
    from bim.commands.query.tui import KanbanTuiApp

    archive_dir = Path(archive_directory).expanduser().resolve() if archive_directory else None
    app = KanbanTuiApp(rows, columns, group_by, archive_dir=archive_dir)
    app.run()


def _write_output(text: str, file: str | None) -> None:
    if file:
        Path(file).write_text(text, encoding="utf-8")
        console.success(f"Written to {file}")
    else:
        console.print(text, mode="raw")
