"""
Tests for the Zettel class.
"""

from datetime import UTC, datetime

import pytest

from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def zettel_data():
    """Fixture that returns a MagicMock object with spec=ZettelData."""
    zettel_data = ZettelData()
    return zettel_data


def test_init_default():
    """Test initializing Zettel with default data."""
    zettel = Zettel()
    assert isinstance(zettel.get_data(), ZettelData)


def test_init_with_data(zettel_data):
    """Test initializing Zettel with provided data."""
    zettel = Zettel(zettel_data)
    assert zettel.get_data() == zettel_data


def test_replace_data(zettel_data):
    """Test replacing Zettel data."""
    zettel = Zettel()
    zettel.replace_data(zettel_data)
    assert zettel.get_data() == zettel_data


def test_alias_attributes(zettel_data):
    """Test aliasing Zettel attributes."""
    zettel_data.metadata = {
        "id": 1,
        "title": "Test Zettel",
        "date": datetime(2023, 1, 1),
    }
    zettel_data.reference = {
        "type": "note",
        "tags": ["test", "pytest"],
        "publish": True,
        "processed": False,
    }
    zettel = Zettel(zettel_data)
    assert zettel.id == 1
    assert zettel.title == "Test Zettel"
    assert zettel.date == datetime(2023, 1, 1)
    assert zettel.type == "note"
    assert zettel.tags == ["pytest", "test"]
    assert zettel.publish is True
    assert zettel.processed is False


def test_id_property(zettel_data):
    """Test the id property."""
    zettel_data.metadata = {"id": 1}
    zettel = Zettel(zettel_data)
    assert zettel.id == 1

    zettel.id = 2
    assert zettel.id == 2

    with pytest.raises(TypeError):
        zettel.id = None

    with pytest.raises(ValueError):
        zettel.id = "invalid"


def test_title_property(zettel_data):
    """Test the title property."""
    zettel_data.metadata = {"title": "Test Zettel"}
    zettel = Zettel(zettel_data)
    assert zettel.title == "Test Zettel"

    zettel.title = "Updated Title"
    assert zettel.title == "Updated Title"

    zettel.title = None
    assert zettel.title == "Updated Title"


def test_date_property(zettel_data):
    """Test the date property."""
    zettel_data.metadata = {"date": datetime(2023, 1, 1)}
    zettel = Zettel(zettel_data)
    assert zettel.date == datetime(2023, 1, 1)

    new_date = datetime(2023, 2, 1)
    zettel.date = new_date
    assert zettel.date == new_date

    zettel.date = None
    assert zettel.date.replace(hour=0, minute=0, second=0) == datetime.now().astimezone(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def test_type_property(zettel_data):
    """Test the type property."""
    zettel_data.metadata = {"type": "note"}
    zettel = Zettel(zettel_data)
    assert zettel.type == "note"

    zettel.type = "article"
    assert zettel.type == "article"

    zettel.type = None
    assert zettel.type == "note"


def test_tags_property(zettel_data):
    """Test the tags property."""
    zettel_data.metadata = {"tags": ["test", "pytest"]}
    zettel = Zettel(zettel_data)
    assert zettel.tags == ["pytest", "test"]

    zettel.tags = ["updated", "tags"]
    assert zettel.tags == ["tags", "updated"]

    zettel.tags = "single-tag"
    assert zettel.tags == ["single-tag"]

    zettel.tags = None
    assert zettel.tags == []


def test_publish_property(zettel_data):
    """Test the publish property."""
    zettel_data.metadata = {"publish": True}
    zettel = Zettel(zettel_data)
    assert zettel.publish is True

    zettel.publish = False
    assert zettel.publish is False


def test_processed_property(zettel_data):
    """Test the processed property."""
    zettel_data.metadata = {"processed": False}
    zettel = Zettel(zettel_data)
    assert zettel.processed is False

    zettel.processed = True
    assert zettel.processed is True
