from __future__ import annotations

from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_type import (
    set_default_type,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSetDefaultType:
    def test_sets_note_on_empty_metadata(self):
        zettel_data = ZettelData()
        set_default_type(zettel_data)
        assert zettel_data.metadata["type"] == "note"

    def test_preserves_other_metadata_keys(self):
        zettel_data = ZettelData()
        zettel_data.metadata["title"] = "hello"
        zettel_data.metadata["tags"] = ["a"]
        set_default_type(zettel_data)
        assert zettel_data.metadata["title"] == "hello"
        assert zettel_data.metadata["tags"] == ["a"]
        assert zettel_data.metadata["type"] == "note"
