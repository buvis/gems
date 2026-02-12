import pytest
from buvis.pybase.zettel.infrastructure.query.query_spec_parser import (
    parse_query_spec,
    parse_query_string,
)


class TestParseQuerySpec:
    def test_minimal_spec(self):
        spec = parse_query_spec({})
        assert spec.source.directory is None
        assert spec.filter is None
        assert spec.sort == []
        assert spec.columns == []

    def test_source_parsing(self):
        spec = parse_query_spec(
            {
                "source": {"directory": "~/notes", "recursive": False, "extensions": ["md", "txt"]},
            }
        )
        assert spec.source.directory == "~/notes"
        assert spec.source.recursive is False
        assert spec.source.extensions == ["md", "txt"]

    def test_simple_filter(self):
        spec = parse_query_spec({"filter": {"type": {"eq": "project"}}})
        assert spec.filter is not None
        assert spec.filter.field == "type"
        assert spec.filter.operator == "eq"
        assert spec.filter.value == "project"

    def test_and_filter(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "and": [
                        {"type": {"eq": "project"}},
                        {"tags": {"contains": "sprint-1"}},
                    ],
                },
            }
        )
        assert spec.filter.combinator == "and"
        assert len(spec.filter.children) == 2
        assert spec.filter.children[0].field == "type"
        assert spec.filter.children[1].field == "tags"

    def test_or_filter(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "or": [
                        {"type": {"eq": "note"}},
                        {"type": {"eq": "project"}},
                    ],
                },
            }
        )
        assert spec.filter.combinator == "or"
        assert len(spec.filter.children) == 2

    def test_not_filter(self):
        spec = parse_query_spec(
            {
                "filter": {"not": {"processed": {"eq": True}}},
            }
        )
        assert spec.filter.combinator == "not"
        assert len(spec.filter.children) == 1
        assert spec.filter.children[0].field == "processed"

    def test_nested_filter(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "and": [
                        {"type": {"eq": "project"}},
                        {"not": {"processed": {"eq": True}}},
                        {
                            "or": [
                                {"tags": {"contains": "a"}},
                                {"tags": {"contains": "b"}},
                            ]
                        },
                    ],
                },
            }
        )
        assert spec.filter.combinator == "and"
        assert len(spec.filter.children) == 3
        assert spec.filter.children[1].combinator == "not"
        assert spec.filter.children[2].combinator == "or"

    def test_sort_parsing(self):
        spec = parse_query_spec(
            {
                "sort": [
                    {"field": "date", "order": "desc"},
                    {"field": "title"},
                ],
            }
        )
        assert len(spec.sort) == 2
        assert spec.sort[0].field == "date"
        assert spec.sort[0].order == "desc"
        assert spec.sort[1].field == "title"
        assert spec.sort[1].order == "asc"

    def test_columns_parsing(self):
        spec = parse_query_spec(
            {
                "columns": [
                    {"field": "id"},
                    {"field": "date", "format": "%Y-%m-%d"},
                    {"expr": "len(tags)", "label": "Tag Count"},
                ],
            }
        )
        assert len(spec.columns) == 3
        assert spec.columns[0].field == "id"
        assert spec.columns[1].format == "%Y-%m-%d"
        assert spec.columns[2].expr == "len(tags)"
        assert spec.columns[2].label == "Tag Count"

    def test_output_parsing(self):
        spec = parse_query_spec(
            {
                "output": {"format": "csv", "file": "out.csv", "limit": 50},
            }
        )
        assert spec.output.format == "csv"
        assert spec.output.file == "out.csv"
        assert spec.output.limit == 50

    def test_invalid_operator(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            parse_query_spec({"filter": {"type": {"bogus": "x"}}})

    def test_column_needs_field_or_expr(self):
        with pytest.raises(ValueError, match="field.*expr"):
            parse_query_spec({"columns": [{"label": "oops"}]})

    def test_expr_filter(self):
        spec = parse_query_spec({"filter": {"expr": "len(tags) > 1"}})
        assert spec.filter.expr == "len(tags) > 1"
        assert spec.filter.field is None
        assert spec.filter.operator is None

    def test_expr_filter_in_and(self):
        spec = parse_query_spec(
            {
                "filter": {
                    "and": [
                        {"type": {"eq": "project"}},
                        {"expr": "len(tags) > 1"},
                    ],
                },
            }
        )
        assert spec.filter.combinator == "and"
        assert spec.filter.children[1].expr == "len(tags) > 1"


class TestParseQueryString:
    def test_inline_yaml(self):
        spec = parse_query_string("{filter: {type: {eq: project}}}")
        assert spec.filter.field == "type"
        assert spec.filter.value == "project"

    def test_invalid_yaml(self):
        with pytest.raises(ValueError, match="YAML mapping"):
            parse_query_string("just a string")
