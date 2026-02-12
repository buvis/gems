import pytest
from buvis.pybase.zettel.domain.entities.project.services.consistency.fixers.normalize_sections_order import (
    normalize_sections_order,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def sample_zettel():
    zettel = ZettelData()
    zettel.sections = [
        ("## Log", ["Log content"]),
        ("# Main", ["Main content"]),
        ("## Description", ["Description content"]),
        ("Other Section", ["Other content"]),
        ("## Actions buffer", ["Actions content"]),
    ]
    return zettel


def test_normalize_sections_order(sample_zettel):
    normalize_sections_order(sample_zettel)

    expected_order = [
        "# Main",
        "## Description",
        "## Log",
        "## Actions buffer",
        "Other Section",
    ]

    assert [section[0] for section in sample_zettel.sections] == expected_order


def test_empty_sections():
    zettel = ZettelData()
    zettel.sections = []
    normalize_sections_order(zettel)
    assert len(zettel.sections) == 0


def test_single_section():
    zettel = ZettelData()
    zettel.sections = [("## Single Section", ["Content"])]
    normalize_sections_order(zettel)
    assert len(zettel.sections) == 1
    assert zettel.sections[0][0] == "## Single Section"


def test_multiple_main_sections():
    zettel = ZettelData()
    zettel.sections = [
        ("# Main 1", ["Content 1"]),
        ("## Description", ["Description"]),
        ("# Main 2", ["Content 2"]),
    ]
    normalize_sections_order(zettel)

    expected_order = ["# Main 1", "## Description", "# Main 2"]

    assert [section[0] for section in zettel.sections] == expected_order


def test_no_special_sections():
    zettel = ZettelData()
    zettel.sections = [
        ("Other Section 1", ["Content 1"]),
        ("Other Section 2", ["Content 2"]),
        ("Other Section 3", ["Content 3"]),
    ]
    normalize_sections_order(zettel)

    expected_order = ["Other Section 1", "Other Section 2", "Other Section 3"]

    assert [section[0] for section in zettel.sections] == expected_order


def test_all_special_sections():
    zettel = ZettelData()
    zettel.sections = [
        ("## Actions buffer", ["Actions"]),
        ("## Log", ["Log"]),
        ("## Description", ["Description"]),
        ("# Main", ["Main"]),
    ]
    normalize_sections_order(zettel)

    expected_order = ["# Main", "## Description", "## Log", "## Actions buffer"]

    assert [section[0] for section in zettel.sections] == expected_order


def test_content_preservation():
    zettel = ZettelData()
    zettel.sections = [
        ("# Main", ["Main content"]),
        ("## Description", ["Description content"]),
    ]
    normalize_sections_order(zettel)

    assert zettel.sections[0][1] == ["Main content"]
    assert zettel.sections[1][1] == ["Description content"]


def test_type_checking():
    with pytest.raises(TypeError):
        normalize_sections_order("Not a ZettelData object")
