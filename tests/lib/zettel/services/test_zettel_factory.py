from __future__ import annotations

from unittest.mock import patch

from buvis.pybase.zettel.domain.entities import ProjectZettel, Zettel
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def _make_zettel(type_value: str, *, from_rust: bool = False) -> Zettel:
    data = ZettelData(metadata={"type": type_value, "title": "Test"})
    return Zettel(data, from_rust=from_rust)


class TestGenericNote:
    def test_empty_type_from_rust(self):
        zettel = _make_zettel("", from_rust=True)
        result = ZettelFactory.create(zettel)
        assert result is zettel
        assert isinstance(result, Zettel)
        assert not isinstance(result, ProjectZettel)

    def test_empty_type_not_from_rust(self):
        zettel = _make_zettel("", from_rust=False)
        with (
            patch.object(Zettel, "ensure_consistency") as mock_ec,
            patch.object(Zettel, "migrate") as mock_mig,
        ):
            result = ZettelFactory.create(zettel)
        assert result is zettel
        assert mock_ec.call_count == 2
        assert mock_mig.call_count == 1

    def test_note_type_from_rust(self):
        zettel = _make_zettel("note", from_rust=True)
        result = ZettelFactory.create(zettel)
        assert result is zettel
        assert isinstance(result, Zettel)

    def test_note_type_not_from_rust(self):
        zettel = _make_zettel("note", from_rust=False)
        with (
            patch.object(Zettel, "ensure_consistency") as mock_ec,
            patch.object(Zettel, "migrate") as mock_mig,
        ):
            result = ZettelFactory.create(zettel)
        assert result is zettel
        assert mock_ec.call_count == 2
        assert mock_mig.call_count == 1


class TestProjectZettel:
    def test_project_from_rust(self):
        zettel = _make_zettel("project", from_rust=True)
        result = ZettelFactory.create(zettel)
        assert isinstance(result, ProjectZettel)
        assert result.from_rust is True
        assert result.get_data() is zettel.get_data()

    def test_project_not_from_rust(self):
        zettel = _make_zettel("project", from_rust=False)
        with (
            patch.object(ProjectZettel, "ensure_consistency") as mock_ec,
            patch.object(ProjectZettel, "migrate") as mock_mig,
        ):
            result = ZettelFactory.create(zettel)
        assert isinstance(result, ProjectZettel)
        assert result.from_rust is False
        assert mock_ec.call_count == 2
        assert mock_mig.call_count == 1


class TestUnknownType:
    def test_unknown_type_from_rust(self):
        zettel = _make_zettel("something_else", from_rust=True)
        result = ZettelFactory.create(zettel)
        assert result is zettel
        assert isinstance(result, Zettel)
        assert not isinstance(result, ProjectZettel)

    def test_unknown_type_not_from_rust(self):
        zettel = _make_zettel("something_else", from_rust=False)
        with (
            patch.object(Zettel, "ensure_consistency") as mock_ec,
            patch.object(Zettel, "migrate") as mock_mig,
        ):
            result = ZettelFactory.create(zettel)
        assert result is zettel
        assert mock_ec.call_count == 2
        assert mock_mig.call_count == 1

    def test_none_type_treated_as_generic(self):
        data = ZettelData(metadata={"title": "Test"})
        zettel = Zettel(data, from_rust=True)
        result = ZettelFactory.create(zettel)
        assert result is zettel
