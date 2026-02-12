import pytest
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.remove_duplicate_tags import (
    remove_duplicate_tags,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def sample_zettel_data():
    """Fixture to create a ZettelData object with initial tags."""
    sample_zettel_date = ZettelData()
    sample_zettel_date.metadata["tags"] = ["python", "code", "python", "test", "code"]
    return sample_zettel_date


def test_remove_duplicate_tags(sample_zettel_data: ZettelData):
    """Test that duplicate tags are removed."""
    remove_duplicate_tags(sample_zettel_data)
    assert sorted(sample_zettel_data.metadata["tags"]) == [
        "code",
        "python",
        "test",
    ], "Tags should be unique and sorted for comparison"


def test_remove_duplicate_tags_no_tags():
    """Test that the function handles cases with no tags gracefully."""
    zettel_data = ZettelData()
    remove_duplicate_tags(zettel_data)
    assert "tags" not in zettel_data.metadata, "No tags key should be present if it was initially absent"


def test_remove_duplicate_tags_unique_tags():
    """Test that the function does not alter tags list if all tags are already unique."""
    zettel_data = ZettelData()
    zettel_data.metadata["tags"] = ["unique", "tags", "test"]
    remove_duplicate_tags(zettel_data)
    assert sorted(zettel_data.metadata["tags"]) == [
        "tags",
        "test",
        "unique",
    ], "Tags should remain unchanged and sorted for comparison"


def test_remove_duplicate_tags_empty_tags():
    """Test that the function handles empty tags list correctly."""
    zettel_data = ZettelData()
    zettel_data.metadata["tags"] = []
    remove_duplicate_tags(zettel_data)
    assert zettel_data.metadata["tags"] == [], "Tags list should remain empty"
