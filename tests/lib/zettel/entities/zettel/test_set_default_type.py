from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_type import (
    DEFAULT_TYPE,
    set_default_type,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_type():
    # Create a MagicMock with spec of ZettelData
    mock_zettel_data = MagicMock(spec=ZettelData)
    mock_zettel_data.metadata = {}

    # Call the function
    set_default_type(mock_zettel_data)

    # Assert that the metadata type is set correctly
    assert mock_zettel_data.metadata["type"] == DEFAULT_TYPE, "The metadata type should be set to the default type"


def test_set_default_type_preserves_other_metadata():
    # Create a MagicMock with spec of ZettelData
    mock_zettel_data = MagicMock(spec=ZettelData)
    mock_zettel_data.metadata = {"author": "John Doe"}

    # Call the function
    set_default_type(mock_zettel_data)

    # Assert that the original metadata is preserved and the type is added
    assert mock_zettel_data.metadata["author"] == "John Doe", "The original metadata should be preserved"
    assert mock_zettel_data.metadata["type"] == DEFAULT_TYPE, "The metadata type should be set to the default type"
