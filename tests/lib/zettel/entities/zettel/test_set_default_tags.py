from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_tags import (
    set_default_tags,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_tags_sets_empty_list():
    zettel_data = ZettelData()
    zettel_data.metadata["tags"] = ["a", "b"]
    set_default_tags(zettel_data)
    assert zettel_data.metadata["tags"] == []
