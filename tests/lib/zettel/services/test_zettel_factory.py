from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.formatting import StringOperator

import buvis.pybase.zettel.domain.entities as zettel_entities
from buvis.pybase.zettel.domain.services.zettel_factory import ZettelFactory


@pytest.fixture
def zettel():
    zettel = MagicMock(spec=zettel_entities.Zettel)
    zettel.get_data = MagicMock(return_value={"some": "data"})
    return zettel


def test_create_with_generic_type(zettel):
    zettel.type = ""
    with patch.object(zettel_entities, "Zettel", return_value=zettel):
        result = ZettelFactory.create(zettel)
        assert result is zettel


def test_create_with_invalid_type(zettel):
    zettel.type = "invalid"
    with (
        patch.object(StringOperator, "camelize", return_value="InvalidZettel"),
        patch.object(zettel_entities, "InvalidZettel", None, create=True),
    ):
        result = ZettelFactory.create(zettel)
        assert result is zettel
