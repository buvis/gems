from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_publish import (
    set_default_publish,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_publish():
    # Create a MagicMock with spec set to ZettelData
    mock_zettel_data = MagicMock(spec=ZettelData)
    mock_zettel_data.metadata = {}

    # Call the function
    set_default_publish(mock_zettel_data)

    # Assert that the publish key is set to False
    assert mock_zettel_data.metadata["publish"] is False
