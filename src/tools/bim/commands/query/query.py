from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.adapters import console
from buvis.pybase.zettel import MarkdownZettelRepository
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase
from buvis.pybase.zettel.infrastructure.query.output_formatter import (
    format_csv,
    format_markdown,
    format_table,
)
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval
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

        repo = MarkdownZettelRepository()
        use_case = QueryZettelsUseCase(repo, python_eval)
        rows = use_case.execute(spec)

        if not rows:
            console.warning("No results")
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


def _write_output(text: str, file: str | None) -> None:
    if file:
        Path(file).write_text(text, encoding="utf-8")
        console.success(f"Written to {file}")
    else:
        console.print(text, mode="raw")
