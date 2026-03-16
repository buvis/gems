from __future__ import annotations

from buvis.pybase.zettel.domain.entities.project.upgrades.migrate_parent_reference import (
    migrate_parent_reference,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestMigrateParentReference:
    def test_no_parent_does_nothing(self) -> None:
        data = ZettelData(metadata={"id": "123", "title": "Test"}, reference={})
        migrate_parent_reference(data)
        assert "parent" not in data.reference

    def test_parent_link_matches_id(self) -> None:
        data = ZettelData(
            metadata={"id": "123", "title": "My Note"},
            reference={"parent": "[[123]]"},
        )
        migrate_parent_reference(data)
        assert data.reference["parent"] == "[[zettelkasten/123|My Note]]"

    def test_parent_link_differs_from_id(self) -> None:
        data = ZettelData(
            metadata={"id": "123", "title": "My Note"},
            reference={"parent": "[[456]]"},
        )
        migrate_parent_reference(data)
        assert data.reference["parent"] == "[[456]]"

    def test_parent_no_wiki_link(self) -> None:
        data = ZettelData(
            metadata={"id": "123", "title": "My Note"},
            reference={"parent": "plain text"},
        )
        migrate_parent_reference(data)
        assert data.reference["parent"] == "plain text"

    def test_parent_empty_string(self) -> None:
        data = ZettelData(
            metadata={"id": "123", "title": "Test"},
            reference={"parent": ""},
        )
        migrate_parent_reference(data)
        assert data.reference["parent"] == ""
