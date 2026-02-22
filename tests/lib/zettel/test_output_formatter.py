from __future__ import annotations

from buvis.pybase.zettel.infrastructure.query.output_formatter import (
    format_csv,
    format_html,
    format_json,
    format_jsonl,
    format_kanban,
    format_markdown,
    format_table,
)

ROWS = [
    {"title": "Note A", "type": "note"},
    {"title": "Note B", "type": "project"},
]
COLS = ["title", "type"]


class TestFormatTable:
    def test_renders_without_error(self) -> None:
        format_table(ROWS, COLS)


class TestFormatCsv:
    def test_header_and_rows(self) -> None:
        out = format_csv(ROWS, COLS)
        lines = out.strip().splitlines()
        assert lines[0].strip() == "title,type"
        assert len(lines) == 3


class TestFormatMarkdown:
    def test_structure(self) -> None:
        out = format_markdown(ROWS, COLS)
        lines = out.strip().split("\n")
        assert "| title | type |" in lines[0]
        assert "---" in lines[1]
        assert len(lines) == 4


class TestFormatJson:
    def test_valid_json(self) -> None:
        import json

        out = format_json(ROWS, COLS)
        data = json.loads(out)
        assert len(data) == 2
        assert data[0]["title"] == "Note A"


class TestFormatJsonl:
    def test_valid_jsonl(self) -> None:
        import json

        out = format_jsonl(ROWS, COLS)
        lines = out.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["title"] == "Note A"


class TestFormatHtml:
    def test_contains_table(self) -> None:
        out = format_html(ROWS, COLS)
        assert "<table>" in out
        assert "Note A" in out


class TestFormatKanban:
    def test_renders_without_error(self) -> None:
        format_kanban(ROWS, COLS, "type")
