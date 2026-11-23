import time
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
            (datetime(2024, 9, 13, 12, tzinfo=timezone(timedelta(hours=2))), 20240913100000),
            (datetime(2024, 9, 13, 4, tzinfo=timezone(timedelta(hours=-6))), 20240913100000),
            (datetime(2024, 9, 13, 11, tzinfo=timezone(timedelta(hours=1))), 20240913100000),
            (datetime(2024, 9, 13, 10, tzinfo=timezone.utc), 20240913100000),
            (datetime(2024, 9, 13, 12, tzinfo=timezone(timedelta(hours=1))), 20240913110000),
            (datetime(2025, 1, 1, 0, 15, 9, tzinfo=timezone(timedelta(hours=5, minutes=30))), 20241231184509),
            (datetime(2023, 12, 31, 23, 45, 7, tzinfo=timezone(timedelta(hours=-5))), 20240101044507),
        ],
        ids=[
            "plus-two",
            "minus-six-same-instant",
            "plus-one-same-instant",
            "utc-same-instant",
            "plus-one-same-wall-clock-other-instant",
            "positive-offset-crosses-back-a-year",
            "negative-offset-crosses-into-next-year",
        ],
    )
    def test_utc_id_ignores_local_offset(self, date: datetime, expected_id: int) -> None:
        zettel_data = ZettelData()
        zettel_data.metadata = {"date": date, "title": "Keep title"}

        set_default_id(zettel_data)

        assert zettel_data.metadata == {"date": date, "id": expected_id, "title": "Keep title"}
        assert zettel_data.metadata["date"] is date

    @pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset is not available on this platform")
    @pytest.mark.parametrize(
        ("date", "expected_id"),
        [
            (datetime(2026, 11, 17, 8, 37, 39), 20261117083739),
            (datetime(2022, 3, 4, 23, 6, 7, 987654), 20220304230607),
        ],
        ids=["morning", "late-evening-with-microseconds"],
    )
    def test_naive_date_keeps_its_digits(
        self, monkeypatch: pytest.MonkeyPatch, date: datetime, expected_id: int
    ) -> None:
        monkeypatch.setenv("TZ", "America/Chicago")
        time.tzset()
        try:
            assert date.astimezone().utcoffset() != timedelta(0)
            zettel_data = ZettelData()
            zettel_data.metadata = {"date": date, "title": "Keep title"}

            set_default_id(zettel_data)

            assert zettel_data.metadata == {"date": date, "id": expected_id, "title": "Keep title"}
            assert zettel_data.metadata["date"] is date
            assert zettel_data.metadata["date"].tzinfo is None
        finally:
            monkeypatch.undo()
            time.tzset()

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
