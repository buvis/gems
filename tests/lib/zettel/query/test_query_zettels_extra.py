from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import (
    QueryZettelsUseCase,
    _apply_operator,
    _extract_metadata_eq,
    _get_field,
)
from buvis.pybase.zettel.domain.value_objects.query_spec import (
    QueryColumn,
    QueryExpand,
    QueryFilter,
    QuerySort,
    QuerySource,
    QuerySpec,
)
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


@pytest.fixture
def zettels_with_lists(make_zettel):
    return [
        make_zettel(
            id=1,
            title="Alpha",
            type="project",
            tags=["sprint-1", "dev"],
            date=datetime(2024, 1, 10, tzinfo=timezone.utc),
            extra_meta={"items": ["a", "b", "c"]},
        ),
        make_zettel(
            id=2,
            title="Beta",
            type="note",
            tags=["sprint-2"],
            date=datetime(2024, 3, 5, tzinfo=timezone.utc),
            extra_meta={"items": ["x", "y"]},
        ),
    ]


class TestExpandBranch:
    def test_expand_produces_one_row_per_item(self, zettels_with_lists):
        repo = MagicMock()
        repo.find_all.return_value = zettels_with_lists

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            expand=QueryExpand(field="items", as_="item"),
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="item", label="item"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        assert len(rows) == 5
        assert rows[0]["item"] == "a"
        assert rows[2]["item"] == "c"
        assert rows[3]["item"] == "x"

    def test_expand_with_filter(self, zettels_with_lists):
        repo = MagicMock()
        repo.find_all.return_value = zettels_with_lists

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            expand=QueryExpand(field="items", as_="item", filter="item != 'a'"),
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="item", label="item"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        assert len(rows) == 4
        assert all(r["item"] != "a" for r in rows)

    def test_expand_with_sort(self, zettels_with_lists):
        repo = MagicMock()
        repo.find_all.return_value = zettels_with_lists

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            expand=QueryExpand(field="items", as_="item"),
            sort=[QuerySort(field="item", order="desc")],
            columns=[
                QueryColumn(expr="item", label="item"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        items = [r["item"] for r in rows]
        assert items == sorted(items, reverse=True)


class TestApplyOperator:
    def test_ge(self):
        assert _apply_operator("ge", 5, 5) is True
        assert _apply_operator("ge", 4, 5) is False

    def test_lt(self):
        assert _apply_operator("lt", 3, 5) is True
        assert _apply_operator("lt", 5, 5) is False

    def test_contains_none(self):
        assert _apply_operator("contains", None, "x") is False

    def test_regex_none(self):
        assert _apply_operator("regex", None, ".*") is False

    def test_unknown_operator(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            _apply_operator("unknown", 1, 1)

    def test_gt_none(self):
        assert _apply_operator("gt", None, 5) is False

    def test_le_none(self):
        assert _apply_operator("le", None, 5) is False

    def test_lt_none(self):
        assert _apply_operator("lt", None, 5) is False


class TestExtractMetadataEq:
    def test_none_filter(self):
        conditions, remaining = _extract_metadata_eq(None)
        assert conditions is None
        assert remaining is None

    def test_non_and_combinator(self):
        f = QueryFilter(combinator="or", children=[])
        conditions, remaining = _extract_metadata_eq(f)
        assert conditions is None
        assert remaining is f

    def test_no_eq_children(self):
        f = QueryFilter(
            combinator="and",
            children=[QueryFilter(operator="gt", field="id", value=5)],
        )
        conditions, remaining = _extract_metadata_eq(f)
        assert conditions is None
        assert remaining is f

    def test_eq_with_expr_skipped(self):
        f = QueryFilter(
            combinator="and",
            children=[QueryFilter(operator="eq", field="type", value="note", expr="x > 1")],
        )
        conditions, remaining = _extract_metadata_eq(f)
        assert conditions is None
        assert remaining is f

    def test_hyphen_to_underscore(self):
        f = QueryFilter(
            combinator="and",
            children=[QueryFilter(operator="eq", field="my-field", value="val")],
        )
        conditions, remaining = _extract_metadata_eq(f)
        assert conditions == {"my_field": "val"}
        assert remaining is f


class TestGetField:
    def test_reference_field(self, make_zettel):
        z = make_zettel(id=1, title="Test")
        z.get_data().reference["source"] = "http://example.com"
        assert _get_field(z, "source") == "http://example.com"

    def test_file_path_field(self, make_zettel):
        z = make_zettel(id=1, title="Test", file_path="/tmp/test.md")
        assert _get_field(z, "file_path") == "/tmp/test.md"

    def test_unknown_field(self, make_zettel):
        z = make_zettel(id=1, title="Test")
        assert _get_field(z, "nonexistent") is None


class TestSortWithNone:
    def test_sort_none_values_last(self, make_zettel):
        repo = MagicMock()
        repo.find_all.return_value = [
            make_zettel(id=1, title=None, type="note"),
            make_zettel(id=2, title="Beta", type="note"),
            make_zettel(id=3, title="Alpha", type="note"),
        ]

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            sort=[QuerySort(field="title", order="asc")],
            columns=[QueryColumn(field="title")],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        assert rows[0]["title"] == "Alpha"
        assert rows[1]["title"] == "Beta"
        assert rows[2]["title"] is None


class TestFilterHyphenField:
    def test_filter_hyphen_field_resolved_via_underscore(self, make_zettel):
        """Filter field 'my-field' resolves to metadata key 'my_field' via replace."""
        repo = MagicMock()
        z = make_zettel(id=1, title="Test", extra_meta={"my_field": "value"})
        repo.find_all.return_value = [z]

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="eq", field="my-field", value="value"),
            columns=[QueryColumn(field="title")],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        assert len(rows) == 1

    def test_filter_underscore_field_falls_back_to_hyphen(self, make_zettel):
        """Filter field 'my_field' falls back to metadata key 'my_field' with hyphen if first lookup is None."""
        repo = MagicMock()
        # Use underscore field in metadata, filter uses underscore too
        z = make_zettel(id=1, title="Test", extra_meta={"my_field": "value"})
        repo.find_all.return_value = [z]

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="eq", field="my_field", value="value"),
            columns=[QueryColumn(field="title")],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        assert len(rows) == 1


class TestDateFormatColumn:
    def test_non_datetime_not_formatted(self, make_zettel):
        repo = MagicMock()
        repo.find_all.return_value = [
            make_zettel(id=1, title="Test", extra_meta={"created": "2024-01-01"}),
        ]

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            columns=[QueryColumn(field="created", format="%Y-%m-%d")],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        # String values are not formatted via strftime
        assert rows[0]["created"] == "2024-01-01"
