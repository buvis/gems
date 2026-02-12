from buvis.pybase.zettel.infrastructure.query.output_formatter import (
    format_csv,
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
