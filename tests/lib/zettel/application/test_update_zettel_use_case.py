from __future__ import annotations

from unittest.mock import MagicMock

from buvis.pybase.zettel.application.use_cases.update_zettel_use_case import UpdateZettelUseCase
from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelWriter


class TestUpdateZettelUseCase:
    def test_updates_metadata(self, make_zettel) -> None:
        writer = MagicMock(spec=ZettelWriter)
        zettel = make_zettel(title="Old")

        UpdateZettelUseCase(writer).execute(zettel, {"title": "New"})

        assert zettel.get_data().metadata["title"] == "New"
        writer.save.assert_called_once_with(zettel)

    def test_updates_reference(self, make_zettel) -> None:
        writer = MagicMock(spec=ZettelWriter)
        zettel = make_zettel()

        UpdateZettelUseCase(writer).execute(zettel, {"source": "http://x"}, "reference")

        assert zettel.get_data().reference["source"] == "http://x"
        writer.save.assert_called_once_with(zettel)

    def test_replaces_existing_section(self, make_zettel) -> None:
        writer = MagicMock(spec=ZettelWriter)
        zettel = make_zettel(sections=[("# Title", "old body")])

        UpdateZettelUseCase(writer).execute(zettel, {"# Title": "new body"}, "section")

        assert zettel.get_data().sections == [("# Title", "new body")]
        writer.save.assert_called_once_with(zettel)

    def test_appends_missing_section(self, make_zettel) -> None:
        writer = MagicMock(spec=ZettelWriter)
        zettel = make_zettel(sections=[("# Existing", "body")])

        UpdateZettelUseCase(writer).execute(zettel, {"# New": "content"}, "section")

        assert zettel.get_data().sections == [("# Existing", "body"), ("# New", "content")]
        writer.save.assert_called_once_with(zettel)

    def test_merges_multiple_metadata_fields(self, make_zettel) -> None:
        writer = MagicMock(spec=ZettelWriter)
        zettel = make_zettel(title="Old", type="note")

        UpdateZettelUseCase(writer).execute(zettel, {"title": "New", "processed": True})

        assert zettel.get_data().metadata == {"title": "New", "type": "note", "processed": True}
