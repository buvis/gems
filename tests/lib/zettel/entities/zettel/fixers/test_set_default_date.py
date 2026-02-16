from datetime import UTC, datetime
from unittest.mock import MagicMock

from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers import set_default_date as date_fixer
from buvis.pybase.zettel.domain.entities.zettel.services.consistency.fixers.set_default_date import (
    set_default_date,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_sets_date_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(date_fixer, "datetime", FixedDateTime)

    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {}

    set_default_date(zettel_data)

    assert zettel_data.metadata["date"] == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_does_not_override_existing_date(monkeypatch) -> None:
    monkeypatch.setattr(date_fixer, "datetime", FixedDateTime)

    existing = datetime(2023, 12, 31, 8, 30, 0, tzinfo=UTC)
    zettel_data = MagicMock(spec=ZettelData)
    zettel_data.metadata = {"date": existing}

    set_default_date(zettel_data)

    assert zettel_data.metadata["date"] == existing
