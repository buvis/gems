from __future__ import annotations

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestZettelData:
    def test_initialization(self):
        zettel = ZettelData()
        assert isinstance(zettel.metadata, dict), "Metadata should be a dictionary"
        assert isinstance(zettel.reference, dict), "Reference should be a dictionary"
        assert isinstance(zettel.sections, list), "Sections should be a list"

    def test_empty_initial_values(self):
        zettel = ZettelData()
        assert zettel.metadata == {}, "Metadata should be initialized to an empty dictionary"
        assert zettel.reference == {}, "Reference should be initialized to an empty dictionary"
        assert zettel.sections == [], "Sections should be initialized to an empty list"
