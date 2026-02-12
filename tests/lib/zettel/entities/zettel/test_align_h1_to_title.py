from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.align_h1_to_title import (
    align_h1_to_title,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_empty_sections():
    zettel = ZettelData()
    zettel.metadata = {"title": "Test Title"}
    zettel.sections = []
    align_h1_to_title(zettel)
    assert zettel.sections == [("# Test Title", "")], "Should add a heading if sections are empty"


def test_incorrect_heading():
    zettel = ZettelData()
    zettel.metadata = {"title": "Test Title"}
    zettel.sections = [("# Incorrect", "Content")]

    align_h1_to_title(zettel)
    assert zettel.sections == [("# Test Title", "Content")], "Should replace incorrect heading with correct one"


def test_correct_heading():
    zettel = ZettelData()
    zettel.metadata = {"title": "Test Title"}
    zettel.sections = [("# Test Title", "Content")]

    align_h1_to_title(zettel)
    assert zettel.sections == [("# Test Title", "Content")], "Should not modify section with correct heading"


def test_non_heading_first_section():
    zettel = ZettelData()
    zettel.metadata = {"title": "Test Title"}
    zettel.sections = [("Not a heading", "Content")]

    align_h1_to_title(zettel)
    assert zettel.sections == [("# Test Title", "Content")], "Should replace non-heading with correct heading"


def test_no_heading_but_empty_string():
    zettel = ZettelData()
    zettel.metadata = {"title": "Test Title"}
    zettel.sections = [("", "Content")]

    align_h1_to_title(zettel)
    assert zettel.sections == [("# Test Title", "Content")], "Should replace empty string with correct heading"
