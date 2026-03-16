from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_id import (
    set_default_id,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSetDefaultId:
    def test_sets_id_from_date(self):
        mock_date = datetime(2024, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
        zettel_data = MagicMock(spec=ZettelData)
        zettel_data.metadata = {"date": mock_date}

        set_default_id(zettel_data)

        assert zettel_data.metadata["id"] == 20240913120000

    def test_raises_on_invalid_date(self):
        zettel_data = MagicMock(spec=ZettelData)
        zettel_data.metadata = {"date": "invalid-date"}

        with pytest.raises(ValueError):
            set_default_id(zettel_data)
