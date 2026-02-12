from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_initialization():
    zettel = ZettelData()
    assert isinstance(zettel.metadata, dict), "Metadata should be a dictionary"
    assert isinstance(zettel.reference, dict), "Reference should be a dictionary"
    assert isinstance(zettel.sections, list), "Sections should be a list"


def test_empty_initial_values():
    zettel = ZettelData()
    assert zettel.metadata == {}, "Metadata should be initialized to an empty dictionary"
    assert zettel.reference == {}, "Reference should be initialized to an empty dictionary"
    assert zettel.sections == [], "Sections should be initialized to an empty list"
