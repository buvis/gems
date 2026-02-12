from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.value_objects.query_spec import (
    QueryColumn,
    QueryFilter,
    QueryOutput,
    QuerySort,
    QuerySource,
    QuerySpec,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.query.expression_engine import python_eval


def _make_zettel(
    *,
    id: int | None = None,
    title: str | None = None,
    date: datetime | None = None,
    type: str | None = None,
    tags: list[str] | None = None,
    processed: bool = False,
    extra_meta: dict | None = None,
) -> Zettel:
    data = ZettelData()
    if id is not None:
        data.metadata["id"] = id
    if title is not None:
        data.metadata["title"] = title
    if date is not None:
        data.metadata["date"] = date
    if type is not None:
        data.metadata["type"] = type
    if tags is not None:
        data.metadata["tags"] = tags
    data.metadata["processed"] = processed
    if extra_meta:
        data.metadata.update(extra_meta)
    data.file_path = f"/notes/{id or 0}.md"
    z = Zettel(data, from_rust=True)
    return z


@pytest.fixture
def sample_zettels():
    return [
        _make_zettel(
            id=1, title="Alpha", type="project", tags=["sprint-1", "dev"], date=datetime(2024, 1, 10, tzinfo=UTC)
        ),
        _make_zettel(id=2, title="Beta", type="note", tags=["sprint-1"], date=datetime(2024, 3, 5, tzinfo=UTC)),
        _make_zettel(
            id=3,
            title="Gamma",
            type="project",
            tags=["sprint-2"],
            date=datetime(2024, 2, 20, tzinfo=UTC),
            processed=True,
        ),
        _make_zettel(id=4, title="Delta", type="note", tags=[], date=datetime(2024, 4, 1, tzinfo=UTC)),
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
