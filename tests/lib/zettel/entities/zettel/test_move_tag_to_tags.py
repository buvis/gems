from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.migration.upgrades.move_tag_to_tags import (
    move_tag_to_tags,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


def test_move_tag_to_tags_with_string_tag():
    # Arrange
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {"tag": "example"}

    # Act
    move_tag_to_tags(zettel_data)

    # Assert
    assert "tag" not in zettel_data.metadata
    assert zettel_data.metadata["tags"] == ["example"]


def test_move_tag_to_tags_with_list_tag():
    # Arrange
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {"tag": ["example1", "example2"]}

    # Act
    move_tag_to_tags(zettel_data)

    # Assert
    assert "tag" not in zettel_data.metadata
    assert zettel_data.metadata["tags"] == ["example1", "example2"]


def test_move_tag_to_tags_with_existing_tags():
    # Arrange
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {"tag": "example", "tags": ["existing"]}

    # Act
    move_tag_to_tags(zettel_data)

    # Assert
    assert "tag" not in zettel_data.metadata
    assert zettel_data.metadata["tags"] == ["existing", "example"]


def test_move_tag_to_tags_no_tag():
    # Arrange
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {"tags": ["existing"]}

    # Act
    move_tag_to_tags(zettel_data)

    # Assert
    assert zettel_data.metadata["tags"] == ["existing"]
