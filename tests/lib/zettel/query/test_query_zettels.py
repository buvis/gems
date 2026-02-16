from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase
from buvis.pybase.zettel.domain.value_objects.query_spec import (
    QueryColumn,
    QueryFilter,
    QueryLookup,
    QueryOutput,
    QuerySort,
    QuerySource,
    QuerySpec,
)
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


@pytest.fixture
def sample_zettels(make_zettel):
    return [
        make_zettel(
            id=1, title="Alpha", type="project", tags=["sprint-1", "dev"], date=datetime(2024, 1, 10, tzinfo=UTC)
        ),
        make_zettel(id=2, title="Beta", type="note", tags=["sprint-1"], date=datetime(2024, 3, 5, tzinfo=UTC)),
        make_zettel(
            id=3,
            title="Gamma",
            type="project",
            tags=["sprint-2"],
            date=datetime(2024, 2, 20, tzinfo=UTC),
            processed=True,
        ),
        make_zettel(id=4, title="Delta", type="note", tags=[], date=datetime(2024, 4, 1, tzinfo=UTC)),
    ]


@pytest.fixture
def mock_repo(sample_zettels):
    repo = MagicMock()
    repo.find_all.return_value = sample_zettels
    return repo


class TestQueryZettelsUseCase:
    def test_no_filter_returns_all(self, mock_repo):
        spec = QuerySpec(source=QuerySource(directory="/notes"))
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 4

    def test_default_columns(self, mock_repo):
        spec = QuerySpec(source=QuerySource(directory="/notes"))
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert set(rows[0].keys()) == {"id", "title", "date", "type", "tags", "file_path"}

    def test_filter_eq(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="eq", field="type", value="project"),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2
        assert all(r["type"] == "project" for r in rows)

    def test_filter_ne(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="ne", field="type", value="project"),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2
        assert all(r["type"] == "note" for r in rows)

    def test_filter_contains(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="contains", field="tags", value="sprint-1"),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_filter_and(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(
                combinator="and",
                children=[
                    QueryFilter(operator="eq", field="type", value="project"),
                    QueryFilter(operator="contains", field="tags", value="sprint-1"),
                ],
            ),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 1
        assert rows[0]["title"] == "Alpha"

    def test_filter_or(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(
                combinator="or",
                children=[
                    QueryFilter(operator="eq", field="id", value=1),
                    QueryFilter(operator="eq", field="id", value=4),
                ],
            ),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_filter_not(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(
                combinator="not",
                children=[QueryFilter(operator="eq", field="processed", value=True)],
            ),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 3

    def test_filter_regex(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="regex", field="title", value="^[AB]"),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_filter_in(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="in", field="type", value=["project", "note"]),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 4

    def test_sort_asc(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            sort=[QuerySort(field="title", order="asc")],
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert [r["title"] for r in rows] == ["Alpha", "Beta", "Delta", "Gamma"]

    def test_sort_desc(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            sort=[QuerySort(field="date", order="desc")],
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert rows[0]["title"] == "Delta"
        assert rows[-1]["title"] == "Alpha"

    def test_limit(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            output=QueryOutput(limit=2),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_sample_reduces_results(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            output=QueryOutput(sample=2),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_sample_larger_than_results_returns_all(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            output=QueryOutput(sample=10),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 4

    def test_sample_after_limit(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            output=QueryOutput(limit=3, sample=2),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_custom_columns(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            columns=[
                QueryColumn(field="id"),
                QueryColumn(field="title"),
            ],
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert set(rows[0].keys()) == {"id", "title"}

    def test_expr_column(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="len(tags)", label="Tag Count"),
            ],
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert rows[0]["Tag Count"] == 2  # Alpha has 2 tags

    def test_date_format_column(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            columns=[
                QueryColumn(field="date", format="%Y-%m-%d"),
            ],
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert rows[0]["date"] == "2024-01-10"

    def test_directory_required(self, mock_repo):
        spec = QuerySpec(source=QuerySource())
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        with pytest.raises(ValueError, match="directory"):
            uc.execute(spec)

    def test_filter_gt(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="gt", field="id", value=2),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2
        assert all(r["id"] > 2 for r in rows)

    def test_filter_le(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(operator="le", field="id", value=2),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_filter_expr(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(expr="len(tags) > 1"),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 1
        assert rows[0]["title"] == "Alpha"

    def test_filter_expr_in_and(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(
                combinator="and",
                children=[
                    QueryFilter(operator="eq", field="type", value="project"),
                    QueryFilter(expr="len(tags) >= 1"),
                ],
            ),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 2

    def test_filter_expr_attribute_access(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            filter=QueryFilter(expr="title.startswith('A')"),
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 1
        assert rows[0]["title"] == "Alpha"

    def test_expr_column_method_call(self, mock_repo):
        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            columns=[
                QueryColumn(expr="title.upper()", label="upper"),
            ],
        )
        uc = QueryZettelsUseCase(mock_repo, python_eval)
        rows = uc.execute(spec)
        assert rows[0]["upper"] == "ALPHA"


def _kanban_zettels(make_zettel):
    """Create zettels for the kanban lookup pool."""
    z1 = make_zettel(id=100, title="US-1234 Implement feature", type="note")
    z2 = make_zettel(id=101, title="US-5678 Fix bug", type="note")
    z3 = make_zettel(id=102, title="Standup notes", type="meeting")
    return [z1, z2, z3]


class TestLookups:
    def _make_repo(self, primary, kanban):
        """Mock repo returning different zettels per directory."""
        repo = MagicMock()

        def find_all(directory, metadata_eq=None):
            if "kanban" in directory:
                return kanban
            return primary

        repo.find_all.side_effect = find_all
        return repo

    def test_lookup_match_filters_candidates(self, make_zettel):
        primary = [
            make_zettel(id=1, title="Project A", type="project", extra_meta={"us": "US-1234"}),
            make_zettel(id=2, title="Project B", type="project", extra_meta={"us": "US-9999"}),
        ]
        kanban = _kanban_zettels(make_zettel)
        repo = self._make_repo(primary, kanban)

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            lookups=[
                QueryLookup(
                    name="kanban",
                    source=QuerySource(directory="/kanban"),
                    match="us and us in kanban.title",
                ),
            ],
            filter=QueryFilter(expr="len(kanban) > 0"),
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="kanban[0].title if kanban else ''", label="kanban_title"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)

        assert len(rows) == 1
        assert rows[0]["title"] == "Project A"
        assert rows[0]["kanban_title"] == "US-1234 Implement feature"

    def test_lookup_no_match_returns_all(self, make_zettel):
        primary = [make_zettel(id=1, title="P1", type="project")]
        kanban = _kanban_zettels(make_zettel)
        repo = self._make_repo(primary, kanban)

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            lookups=[
                QueryLookup(
                    name="kanban",
                    source=QuerySource(directory="/kanban"),
                    # no match → cross join
                ),
            ],
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="len(kanban)", label="count"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            rows = uc.execute(spec)
            assert len(w) == 1
            assert "cross-joining" in str(w[0].message)

        assert len(rows) == 1
        assert rows[0]["count"] == 3  # all kanban candidates

    def test_lookup_filter_expr_uses_lookup(self, make_zettel):
        primary = [
            make_zettel(id=1, title="Has match", type="project", extra_meta={"us": "US-1234"}),
            make_zettel(id=2, title="No match", type="project", extra_meta={"us": "NOPE"}),
        ]
        kanban = _kanban_zettels(make_zettel)
        repo = self._make_repo(primary, kanban)

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            lookups=[
                QueryLookup(
                    name="kanban",
                    source=QuerySource(directory="/kanban"),
                    match="us and us in kanban.title",
                ),
            ],
            filter=QueryFilter(expr="len(kanban) > 0"),
            columns=[QueryColumn(field="title")],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)
        assert len(rows) == 1
        assert rows[0]["title"] == "Has match"

    def test_lookup_column_expr(self, make_zettel):
        primary = [
            make_zettel(id=1, title="P1", type="project", extra_meta={"us": "US-5678"}),
        ]
        kanban = _kanban_zettels(make_zettel)
        repo = self._make_repo(primary, kanban)

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            lookups=[
                QueryLookup(
                    name="kanban",
                    source=QuerySource(directory="/kanban"),
                    match="us and us in kanban.title",
                ),
            ],
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="kanban[0].title if kanban else ''", label="k_title"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)
        assert rows[0]["k_title"] == "US-5678 Fix bug"

    def test_lookup_no_candidates(self, make_zettel):
        primary = [
            make_zettel(id=1, title="P1", type="project", extra_meta={"us": "NOPE"}),
        ]
        kanban = _kanban_zettels(make_zettel)
        repo = self._make_repo(primary, kanban)

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            lookups=[
                QueryLookup(
                    name="kanban",
                    source=QuerySource(directory="/kanban"),
                    match="us and us in kanban.title",
                ),
            ],
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="len(kanban)", label="count"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)
        assert rows[0]["count"] == 0

    def test_lookup_with_pre_filter(self, make_zettel):
        primary = [
            make_zettel(id=1, title="P1", type="project", extra_meta={"us": "US-1234"}),
        ]
        kanban = _kanban_zettels(make_zettel)
        repo = self._make_repo(primary, kanban)

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            lookups=[
                QueryLookup(
                    name="kanban",
                    source=QuerySource(directory="/kanban"),
                    filter=QueryFilter(operator="eq", field="type", value="note"),
                    match="us and us in kanban.title",
                ),
            ],
            columns=[
                QueryColumn(field="title"),
                QueryColumn(expr="len(kanban)", label="count"),
            ],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        rows = uc.execute(spec)
        # pre-filter removes meeting (type=meeting), match on title gives 1
        assert rows[0]["count"] == 1

    def test_lookup_missing_directory_raises(self, make_zettel):
        repo = MagicMock()
        repo.find_all.return_value = [make_zettel(id=1, title="P1", type="project")]

        spec = QuerySpec(
            source=QuerySource(directory="/notes"),
            lookups=[
                QueryLookup(name="bad"),
            ],
            columns=[QueryColumn(field="title")],
        )
        uc = QueryZettelsUseCase(repo, python_eval)
        with pytest.raises(ValueError, match="directory"):
            uc.execute(spec)
