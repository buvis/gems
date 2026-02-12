from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_tags import (
    set_default_tags,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_tags_no_metadata():
    mock_zettel_data = MagicMock(spec=ZettelData)
    del mock_zettel_data.metadata  # Simulate missing metadata
    with pytest.raises(AttributeError):
        set_default_tags(mock_zettel_data)
