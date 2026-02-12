from buvis.pybase.zettel.domain.value_objects.query_spec import (
    QueryColumn,
    QueryFilter,
    QueryOutput,
    QuerySort,
    QuerySource,
    QuerySpec,
)


class TestQuerySpecDataclasses:
    def test_query_source_defaults(self):
        s = QuerySource()
        assert s.directory is None
        assert s.recursive is True
        assert s.extensions == ["md"]

    def test_query_filter_field_condition(self):
        f = QueryFilter(operator="eq", field="type", value="project")
        assert f.operator == "eq"
        assert f.field == "type"
        assert f.value == "project"
        assert f.combinator is None
        assert f.children == []

    def test_query_filter_combinator(self):
        c1 = QueryFilter(operator="eq", field="type", value="project")
        c2 = QueryFilter(operator="contains", field="tags", value="sprint-1")
        f = QueryFilter(combinator="and", children=[c1, c2])
        assert f.combinator == "and"
        assert len(f.children) == 2

    def test_query_sort(self):
        s = QuerySort(field="date", order="desc")
        assert s.field == "date"
        assert s.order == "desc"

    def test_query_sort_default_order(self):
        s = QuerySort(field="title")
        assert s.order == "asc"

    def test_query_column_field(self):
        c = QueryColumn(field="title")
        assert c.field == "title"
        assert c.expr is None

    def test_query_column_expr(self):
        c = QueryColumn(expr="len(tags)", label="Tag Count")
        assert c.expr == "len(tags)"
        assert c.label == "Tag Count"

    def test_query_output_defaults(self):
        o = QueryOutput()
        assert o.format == "table"
        assert o.file is None
        assert o.limit is None

    def test_query_spec_defaults(self):
        spec = QuerySpec()
        assert spec.source.directory is None
        assert spec.filter is None
        assert spec.sort == []
        assert spec.columns == []
        assert spec.output.format == "table"
