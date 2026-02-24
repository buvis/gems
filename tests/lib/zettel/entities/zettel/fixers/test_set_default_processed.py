from __future__ import annotations

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_processed import (
    set_default_processed,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSetDefaultProcessed:
    def test_sets_false_on_empty_metadata(self):
        zettel_data = ZettelData()
        set_default_processed(zettel_data)
        assert zettel_data.metadata["processed"] is False

    def test_preserves_other_metadata_keys(self):
        zettel_data = ZettelData()
        zettel_data.metadata["title"] = "hello"
        zettel_data.metadata["tags"] = ["a"]
        set_default_processed(zettel_data)
        assert zettel_data.metadata["title"] == "hello"
        assert zettel_data.metadata["tags"] == ["a"]
        assert zettel_data.metadata["processed"] is False
