from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.domain.entities.zettel.services.migration.upgrades.normalize_type import (
    normalize_type,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def mock_zettel_data() -> MagicMock:
    """Fixture to create a mock ZettelData object."""
    zettel = MagicMock(spec=ZettelData)
    zettel.metadata = {}
    return zettel


@pytest.mark.parametrize(
    "original_type, expected_type",
    [
        ("loop", "project"),
        ("wiki-article", "note"),
        ("zettel", "note"),
        ("dummy", "dummy"),
    ],
)
def test_normalize_type(mock_zettel_data: MagicMock, original_type: str, expected_type: str):
    """Test the normalize_type function to ensure it correctly updates the zettel's type."""
    mock_zettel_data.metadata["type"] = original_type
    normalize_type(mock_zettel_data)
    assert mock_zettel_data.metadata["type"] == expected_type, "The zettel type was not normalized correctly."
