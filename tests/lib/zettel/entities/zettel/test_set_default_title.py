from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_title import (
    DEFAULT_TITLE,
    set_default_title,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_set_default_title():
    mock_zettel_data = MagicMock(spec=ZettelData)
    mock_zettel_data.metadata = {}
    mock_zettel_data.sections = [("# My Title", "Content")]

    set_default_title(mock_zettel_data)
    assert mock_zettel_data.metadata["title"] == "My Title"
    del mock_zettel_data.metadata["title"]

    # Test with no sections
    mock_zettel_data.sections = []
    set_default_title(mock_zettel_data)
    assert mock_zettel_data.metadata["title"] == DEFAULT_TITLE
    del mock_zettel_data.metadata["title"]

    # Test with no heading marker
    mock_zettel_data.sections = [("My Title", "Content")]
    set_default_title(mock_zettel_data)
    assert mock_zettel_data.metadata["title"] == DEFAULT_TITLE
