from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_id import (
    set_default_id,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_id():
    # Mock ZettelData with a specific datetime
    mock_date = datetime(2024, 9, 13, 12, 0, 0, tzinfo=UTC)
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {"date": mock_date}

    # Function under test
    set_default_id(zettel_data)

    # Expected ID format
    expected_id = 20240913120000
    assert zettel_data.metadata["id"] == expected_id, "The ID should be set based on the UTC datetime."


def test_set_default_id_with_invalid_date():
    # Mock ZettelData with non-datetime type to force error
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {"date": "invalid-date"}

    # Expect ValueError on invalid date format
    with pytest.raises(ValueError):
        set_default_id(zettel_data)
