from datetime import UTC
from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_date():
    """
    Test the set_default_date function to ensure it sets the correct UTC date.
    """
    mock_zettel_data = MagicMock(spec=ZettelData)
    mock_zettel_data.metadata = {}

    from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_date import (
        set_default_date,
    )

    set_default_date(mock_zettel_data)

    assert "date" in mock_zettel_data.metadata, "Date key should be present in metadata"
    assert mock_zettel_data.metadata["date"].tzinfo is UTC, "The date should be set with UTC timezone"
