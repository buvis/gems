"""
Test cases for the ZettelConsistencyService class.
"""

from datetime import UTC, datetime

import pytest

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.zettel_consistency_service import (
    ZettelConsistencyService,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def zettel_data() -> ZettelData:
    """
    Fixture that returns a ZettelData instance with minimal metadata.
    """
    zettel_data = ZettelData()
    zettel_data.metadata = {"content": "Test content"}
    return zettel_data


def test_set_missing_defaults(zettel_data: ZettelData) -> None:
    """
    Test that set_missing_defaults sets default values for missing metadata fields.
    """
    ZettelConsistencyService.set_missing_defaults(zettel_data)

    assert zettel_data.metadata["date"] == datetime.now(UTC).replace(microsecond=0)
    assert zettel_data.metadata["id"] is not None
    assert zettel_data.metadata["title"] == "Unknown title"
    assert zettel_data.metadata["type"] == "note"
    assert zettel_data.metadata["tags"] == []
    assert zettel_data.metadata["publish"] is False
    assert zettel_data.metadata["processed"] is False


def test_ensure_consistency(zettel_data: ZettelData) -> None:
    """
    Test that ensure_consistency sets missing defaults and applies consistency fixes.
    """
    zettel_data.metadata["tags"] = ["tag1", "tag2", "tag1"]
    zettel_data.metadata["title"] = "  test title  "
    zettel_data.sections = [("# Different Title", "\n\nTest content")]

    ZettelConsistencyService.ensure_consistency(zettel_data)

    assert zettel_data.metadata["tags"] == ["tag1", "tag2"]
    assert zettel_data.metadata["title"] == "Test title"
    assert zettel_data.sections == [("# Test title", "\n\nTest content")]


@pytest.mark.parametrize(
    "metadata",
    [
        {"date": datetime.now(UTC).replace(microsecond=0)},
        {"id": "test-id"},
        {"title": "Test Title"},
        {"type": "article"},
        {"tags": ["tag1", "tag2"]},
        {"publish": True},
        {"processed": True},
    ],
)
def test_set_missing_defaults_with_existing_metadata(zettel_data: ZettelData, metadata: dict[str, object]) -> None:
    """
    Test that set_missing_defaults does not overwrite existing metadata values.
    """
    zettel_data.metadata.update(metadata)
    ZettelConsistencyService.set_missing_defaults(zettel_data)

    for key, value in metadata.items():
        assert zettel_data.metadata[key] == value
