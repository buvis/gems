from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_title import (
    DEFAULT_TITLE,
    set_default_title,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSetDefaultTitle:
    def test_sets_title_from_heading(self):
        mock_zettel_data = MagicMock(spec=ZettelData)
        mock_zettel_data.metadata = {}
        mock_zettel_data.sections = [("# My Title", "Content")]

        set_default_title(mock_zettel_data)
        assert mock_zettel_data.metadata["title"] == "My Title"

    def test_sets_default_when_no_sections(self):
        mock_zettel_data = MagicMock(spec=ZettelData)
        mock_zettel_data.metadata = {}
        mock_zettel_data.sections = []

        set_default_title(mock_zettel_data)
        assert mock_zettel_data.metadata["title"] == DEFAULT_TITLE

    def test_sets_default_when_no_heading_marker(self):
        mock_zettel_data = MagicMock(spec=ZettelData)
        mock_zettel_data.metadata = {}
        mock_zettel_data.sections = [("My Title", "Content")]

        set_default_title(mock_zettel_data)
        assert mock_zettel_data.metadata["title"] == DEFAULT_TITLE
