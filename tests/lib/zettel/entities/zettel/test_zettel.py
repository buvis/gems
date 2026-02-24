from datetime import datetime

import pytest
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


@pytest.fixture
def zettel_data():
    return ZettelData()


class TestZettelInit:
    def test_default(self):
        zettel = Zettel()
        assert isinstance(zettel.get_data(), ZettelData)

    def test_with_data(self, zettel_data):
        zettel = Zettel(zettel_data)
        assert zettel.get_data() == zettel_data

    def test_replace_data(self, zettel_data):
        zettel = Zettel()
        zettel.replace_data(zettel_data)
        assert zettel.get_data() == zettel_data


class TestZettelProperties:
    def test_explicit_properties(self, zettel_data):
        zettel_data.metadata = {
            "id": 1,
            "title": "Test Zettel",
            "date": datetime(2023, 1, 1),
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
        assert zettel.tags == ["test", "pytest"]
        assert zettel.publish is True
        assert zettel.processed is False

    def test_id(self, zettel_data):
        zettel_data.metadata = {"id": 1}
        zettel = Zettel(zettel_data)
        assert zettel.id == 1

        zettel.id = 2
        assert zettel.id == 2

        with pytest.raises(TypeError):
            zettel.id = None

        with pytest.raises(ValueError):
            zettel.id = "invalid"

    def test_title(self, zettel_data):
        zettel_data.metadata = {"title": "Test Zettel"}
        zettel = Zettel(zettel_data)
        assert zettel.title == "Test Zettel"

        zettel.title = "Updated Title"
        assert zettel.title == "Updated Title"

        zettel.title = None
        assert zettel.title is None

    def test_date(self, zettel_data):
        zettel_data.metadata = {"date": datetime(2023, 1, 1)}
        zettel = Zettel(zettel_data)
        assert zettel.date == datetime(2023, 1, 1)

        new_date = datetime(2023, 2, 1)
        zettel.date = new_date
        assert zettel.date == new_date

        zettel.date = None
        assert zettel.date is None

    def test_type(self, zettel_data):
        zettel_data.metadata = {"type": "note"}
        zettel = Zettel(zettel_data)
        assert zettel.type == "note"

        zettel.type = "article"
        assert zettel.type == "article"

        zettel.type = None
        assert zettel.type is None

    def test_tags(self, zettel_data):
        zettel_data.metadata = {"tags": ["test", "pytest"]}
        zettel = Zettel(zettel_data)
        assert zettel.tags == ["test", "pytest"]

        zettel.tags = ["updated", "tags"]
        assert zettel.tags == ["updated", "tags"]

        zettel.tags = "single-tag"
        assert zettel.tags == ["single-tag"]

        zettel.tags = None
        assert zettel.tags is None

    def test_publish(self, zettel_data):
        zettel_data.metadata = {"publish": True}
        zettel = Zettel(zettel_data)
        assert zettel.publish is True

        zettel.publish = False
        assert zettel.publish is False

    def test_processed(self, zettel_data):
        zettel_data.metadata = {"processed": False}
        zettel = Zettel(zettel_data)
        assert zettel.processed is False

        zettel.processed = True
        assert zettel.processed is True
