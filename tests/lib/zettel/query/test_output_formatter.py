import json

import pytest
from buvis.pybase.zettel.infrastructure.query.output_formatter import (
    format_csv,
    format_html,
    format_json,
    format_jsonl,
    format_kanban,
    format_markdown,
)


class TestFormatCsv:
    def test_basic(self):
        rows = [
            {"id": 1, "title": "Alpha"},
            {"id": 2, "title": "Beta"},
        ]
        result = format_csv(rows, ["id", "title"])
        lines = result.strip().splitlines()
        assert lines[0] == "id,title"
        assert lines[1] == "1,Alpha"
        assert lines[2] == "2,Beta"

    def test_empty_rows(self):
        result = format_csv([], ["id", "title"])
        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert lines[0] == "id,title"

    def test_missing_column(self):
        rows = [{"id": 1}]
        result = format_csv(rows, ["id", "title"])
        assert ",," not in result  # empty string, not missing


class TestFormatMarkdown:
    def test_basic(self):
        rows = [
            {"id": 1, "title": "Alpha"},
            {"id": 2, "title": "Beta"},
        ]
        result = format_markdown(rows, ["id", "title"])
        lines = result.strip().split("\n")
        assert lines[0] == "| id | title |"
        assert lines[1] == "| --- | --- |"
        assert lines[2] == "| 1 | Alpha |"
        assert lines[3] == "| 2 | Beta |"

    def test_pipe_escaping(self):
        rows = [{"val": "a|b"}]
        result = format_markdown(rows, ["val"])
        assert "a\\|b" in result

    def test_empty_rows(self):
        result = format_markdown([], ["id"])
        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + separator only


SAMPLE_ROWS = [
    {"id": 1, "title": "Alpha", "extra": "x"},
    {"id": 2, "title": "Beta", "extra": "y"},
]
SAMPLE_COLS = ["id", "title"]


class TestFormatJson:
    def test_basic(self):
        result = format_json(SAMPLE_ROWS, SAMPLE_COLS)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0] == {"id": 1, "title": "Alpha"}
        assert parsed[1] == {"id": 2, "title": "Beta"}

    def test_empty_rows(self):
        result = format_json([], SAMPLE_COLS)
        assert json.loads(result) == []

    def test_column_filtering(self):
        result = format_json(SAMPLE_ROWS, SAMPLE_COLS)
        parsed = json.loads(result)
        for row in parsed:
            assert "extra" not in row


class TestFormatJsonl:
    def test_basic(self):
        result = format_jsonl(SAMPLE_ROWS, SAMPLE_COLS)
        lines = result.strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"id": 1, "title": "Alpha"}
        assert json.loads(lines[1]) == {"id": 2, "title": "Beta"}

    def test_empty_rows(self):
        result = format_jsonl([], SAMPLE_COLS)
        assert result.strip() == ""

    def test_column_filtering(self):
        result = format_jsonl(SAMPLE_ROWS, SAMPLE_COLS)
        for line in result.strip().splitlines():
            assert "extra" not in json.loads(line)


class TestFormatHtml:
    def test_basic(self):
        result = format_html(SAMPLE_ROWS, SAMPLE_COLS)
        assert "<th>id</th>" in result
        assert "<th>title</th>" in result
        assert "<td>1</td>" in result
        assert "<td>Alpha</td>" in result

    def test_empty_rows(self):
        result = format_html([], SAMPLE_COLS)
        assert "<th>id</th>" in result
        assert "<td>" not in result

    def test_xss_escaping(self):
        rows = [{"val": "<script>alert(1)</script>"}]
        result = format_html(rows, ["val"])
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestFormatKanban:
    def test_groups_by_field(self, capsys):
        rows = [
            {"title": "Task A", "status": "todo"},
            {"title": "Task B", "status": "done"},
            {"title": "Task C", "status": "todo"},
        ]
        format_kanban(rows, ["title", "status"], "status")
        out = capsys.readouterr().out
        assert "todo" in out
        assert "done" in out
        assert "Task A" in out
        assert "Task B" in out

    def test_ungrouped(self, capsys):
        rows = [
            {"title": "No Group", "status": None},
            {"title": "Empty", "status": ""},
        ]
        format_kanban(rows, ["title", "status"], "status")
        out = capsys.readouterr().out
        assert "Ungrouped" in out


class TestFormatPdf:
    def test_basic(self):
        fpdf = pytest.importorskip("fpdf")  # noqa: F841
        from buvis.pybase.zettel.infrastructure.query.output_formatter import format_pdf

        result = format_pdf(SAMPLE_ROWS, SAMPLE_COLS)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_empty_rows(self):
        fpdf = pytest.importorskip("fpdf")  # noqa: F841
        from buvis.pybase.zettel.infrastructure.query.output_formatter import format_pdf

        result = format_pdf([], SAMPLE_COLS)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
