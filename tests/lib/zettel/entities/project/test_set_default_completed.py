from __future__ import annotations

from buvis.pybase.zettel.domain.entities.project.fixers.set_default_completed import (
    set_default_completed,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSetDefaultCompleted:
    def test_sets_false_on_empty_metadata(self):
        zettel_data = ZettelData()
        set_default_completed(zettel_data)
        assert zettel_data.metadata["completed"] is False

    def test_preserves_other_metadata_keys(self):
        zettel_data = ZettelData()
        zettel_data.metadata["title"] = "hello"
        zettel_data.metadata["tags"] = ["a"]
        set_default_completed(zettel_data)
        assert zettel_data.metadata["title"] == "hello"
        assert zettel_data.metadata["tags"] == ["a"]
        assert zettel_data.metadata["completed"] is False

    def test_does_not_overwrite_existing_true(self):
        zettel_data = ZettelData()
        zettel_data.metadata["completed"] = True
        set_default_completed(zettel_data)
        assert zettel_data.metadata["completed"] is True

    def test_migrates_gtd_list_completed(self):
        zettel_data = ZettelData()
        zettel_data.metadata["gtd-list"] = "completed"
        set_default_completed(zettel_data)
        assert zettel_data.metadata["completed"] is True
        assert "gtd-list" not in zettel_data.metadata

    def test_ignores_gtd_list_other_value(self):
        zettel_data = ZettelData()
        zettel_data.metadata["gtd-list"] = "next"
        set_default_completed(zettel_data)
        assert zettel_data.metadata["completed"] is False
        assert zettel_data.metadata["gtd-list"] == "next"
