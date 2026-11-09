from datetime import date, datetime, timedelta, timezone

import pytest
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_id import (
    set_default_id,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData


class TestSetDefaultId:
    @pytest.mark.parametrize(
        ("date", "expected_id"),
        [
            (datetime(2024, 9, 13, 12, tzinfo=timezone(timedelta(hours=2))), 20240913120000),
            (datetime(2024, 9, 13, 10, tzinfo=timezone.utc), 20240913100000),
            (datetime(2025, 1, 1, 0, 15, 9, tzinfo=timezone(timedelta(hours=5, minutes=30))), 20250101001509),
            (datetime(2023, 12, 31, 23, 45, 7, tzinfo=timezone(timedelta(hours=-5))), 20231231234507),
            (datetime(2022, 3, 4, 5, 6, 7, 987654), 20220304050607),
        ],
        ids=["local-offset", "same-instant-utc", "positive-offset-midnight", "negative-offset-midnight", "naive"],
    )
    def test_sets_id_from_dates_own_wall_clock(self, date: datetime, expected_id: int) -> None:
        zettel_data = ZettelData()
        zettel_data.metadata = {"date": date, "title": "Keep title"}

        set_default_id(zettel_data)

        assert zettel_data.metadata == {"date": date, "id": expected_id, "title": "Keep title"}
        assert zettel_data.metadata["date"] is date

    @pytest.mark.parametrize(
        "date",
        [
            "invalid-date",
            "2024-09-13T12:00:00+02:00",
            "",
            None,
            20240913120000,
            pytest.param(date(2024, 9, 13), id="date-only"),
        ],
    )
    def test_raises_on_invalid_date(self, date: object) -> None:
        zettel_data = ZettelData()
        zettel_data.metadata = {"date": date}

        with pytest.raises(ValueError, match="^Invalid date format$"):
            set_default_id(zettel_data)

        assert "id" not in zettel_data.metadata
