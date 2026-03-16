from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_tags import (
    set_default_tags,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSetDefaultTags:
    def test_sets_empty_list(self):
        zettel_data = ZettelData()
        zettel_data.metadata["tags"] = ["a", "b"]
        set_default_tags(zettel_data)
        assert zettel_data.metadata["tags"] == []
