from __future__ import annotations

from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.fixers.sort_tags import (
    sort_tags,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSortTags:
    def test_sort_tags(self):
        # Create a MagicMock with spec of ZettelData
        mock_zettel_data = MagicMock(spec=ZettelData)
        mock_zettel_data.metadata = {"tags": ["banana", "apple", "cherry"]}

        # Call the function
        sort_tags(mock_zettel_data)

        # Assert the tags are sorted
        assert mock_zettel_data.metadata["tags"] == ["apple", "banana", "cherry"]

    def test_sort_tags_empty(self):
        # Create a MagicMock with spec of ZettelData
        mock_zettel_data = MagicMock(spec=ZettelData)
        mock_zettel_data.metadata = {"tags": []}

        # Call the function
        sort_tags(mock_zettel_data)

        # Assert the tags are empty
        assert mock_zettel_data.metadata["tags"] == []
