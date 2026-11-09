import os
import sys
import time
from datetime import datetime, timedelta, timezone, tzinfo

import pytest
from buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_date import (
    set_default_date,
)
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData

_date_mod = sys.modules["buvis.pybase.zettel.domain.entities.zettel.fixers.set_default_date"]


class TestSetDefaultDate:
    @pytest.mark.skipif(not hasattr(time, "tzset"), reason="Controlled system timezone requires time.tzset")
    @pytest.mark.parametrize("metadata", [{}, {"date": None, "title": "Keep title"}])
    @pytest.mark.parametrize(
        ("local_timezone", "moment"),
        [
            ("UTC-2", datetime(2024, 1, 1, 0, 15, 9, 987654, tzinfo=timezone(timedelta(hours=2)))),
            ("UTC+5", datetime(2025, 6, 30, 23, 45, 7, 123456, tzinfo=timezone(timedelta(hours=-5)))),
        ],
        ids=["east-of-utc", "west-of-utc"],
    )
    def test_sets_local_date_without_microseconds(
        self, monkeypatch: pytest.MonkeyPatch, metadata: dict[str, object], local_timezone: str, moment: datetime
    ) -> None:
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> datetime:
                return moment.replace(tzinfo=None) if tz is None else moment.astimezone(tz)

        original_timezone = os.environ.get("TZ")
        monkeypatch.setenv("TZ", local_timezone)
        time.tzset()
        monkeypatch.setattr(_date_mod, "datetime", FixedDateTime)
        zettel_data = ZettelData()
        zettel_data.metadata = metadata.copy()

        try:
            set_default_date(zettel_data)

            actual = zettel_data.metadata["date"]
            assert actual.isoformat() == moment.replace(microsecond=0).isoformat()
            assert actual.utcoffset() == moment.utcoffset()
            assert zettel_data.metadata == {**metadata, "date": moment.replace(microsecond=0)}
        finally:
            if original_timezone is None:
                monkeypatch.delenv("TZ", raising=False)
            else:
                monkeypatch.setenv("TZ", original_timezone)
            time.tzset()

    @pytest.mark.parametrize(
        "existing",
        [
            datetime(2023, 12, 31, 8, 30, 0, tzinfo=timezone.utc),
            datetime(2025, 7, 1, 1, 2, 3, 456789, tzinfo=timezone(timedelta(hours=5, minutes=30))),
            datetime(2022, 2, 3, 4, 5, 6),
            "",
            False,
        ],
    )
    def test_does_not_override_existing_date(self, existing: object) -> None:
        zettel_data = ZettelData()
        zettel_data.metadata = {"date": existing, "title": "Keep title"}

        set_default_date(zettel_data)

        assert zettel_data.metadata["date"] is existing
        assert zettel_data.metadata["title"] == "Keep title"
