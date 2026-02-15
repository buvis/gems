from __future__ import annotations

from unittest.mock import MagicMock

from buvis.pybase.zettel.application.use_cases.update_zettel_use_case import UpdateZettelUseCase
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def _make_zettel(data: ZettelData) -> Zettel:
    mock = MagicMock(spec=Zettel)
    mock.get_data.return_value = data
    return mock


class TestUpdateZettelUseCase:
    def test_updates_metadata(self) -> None:
        writer = MagicMock(spec=ZettelWriter)
        data = ZettelData()
        data.metadata = {"title": "Old"}
        zettel = _make_zettel(data)

        UpdateZettelUseCase(writer).execute(zettel, {"title": "New"})

        assert data.metadata["title"] == "New"
        writer.save.assert_called_once_with(zettel)

    def test_updates_reference(self) -> None:
        writer = MagicMock(spec=ZettelWriter)
        data = ZettelData()
        data.reference = {}
        zettel = _make_zettel(data)

        UpdateZettelUseCase(writer).execute(zettel, {"source": "http://x"}, "reference")

        assert data.reference["source"] == "http://x"
        writer.save.assert_called_once_with(zettel)

    def test_replaces_existing_section(self) -> None:
        writer = MagicMock(spec=ZettelWriter)
        data = ZettelData()
        data.sections = [("# Title", "old body")]
        zettel = _make_zettel(data)

        UpdateZettelUseCase(writer).execute(zettel, {"# Title": "new body"}, "section")

        assert data.sections == [("# Title", "new body")]
        writer.save.assert_called_once_with(zettel)

    def test_appends_missing_section(self) -> None:
        writer = MagicMock(spec=ZettelWriter)
        data = ZettelData()
        data.sections = [("# Existing", "body")]
        zettel = _make_zettel(data)

        UpdateZettelUseCase(writer).execute(zettel, {"# New": "content"}, "section")

        assert data.sections == [("# Existing", "body"), ("# New", "content")]
        writer.save.assert_called_once_with(zettel)

    def test_merges_multiple_metadata_fields(self) -> None:
        writer = MagicMock(spec=ZettelWriter)
        data = ZettelData()
        data.metadata = {"title": "Old", "type": "note"}
        zettel = _make_zettel(data)

        UpdateZettelUseCase(writer).execute(zettel, {"title": "New", "processed": True})

        assert data.metadata == {"title": "New", "type": "note", "processed": True}
