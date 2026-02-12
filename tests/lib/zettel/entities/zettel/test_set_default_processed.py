from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_processed import (
    set_default_processed,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_processed():
    # Create a MagicMock with spec for ZettelData
    mock_zettel_data = MagicMock(spec=ZettelData)
    mock_zettel_data.metadata = {}

    # Call the function
    set_default_processed(mock_zettel_data)

    # Assert that the metadata was set correctly
    assert "processed" in mock_zettel_data.metadata
    assert mock_zettel_data.metadata["processed"] is False
