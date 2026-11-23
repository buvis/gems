import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
    _get_date_from_file,
)

READER = "buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser.FileMetadataReader"
EARLIER_FILE_SYSTEM_DATE = datetime(2001, 2, 3, 4, 5, 6, tzinfo=timezone.utc)


class TestGetDateFromFile:
    @pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset is not available on this platform")
    @pytest.mark.parametrize("local_zone", ["America/Chicago", "Asia/Kolkata"])
    @pytest.mark.parametrize(
        ("file_name", "expected"),
        [
            ("20240115143022 some note.md", datetime(2024, 1, 15, 14, 30, 22, tzinfo=timezone.utc)),
            ("20230704235901.md", datetime(2023, 7, 4, 23, 59, 1, tzinfo=timezone.utc)),
            ("202401151430 some note.md", datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)),
            ("202312310005 other.md", datetime(2023, 12, 31, 0, 5, tzinfo=timezone.utc)),
        ],
        ids=["14-digits", "14-digits-late-evening", "12-digits", "12-digits-just-after-midnight"],
    )
    @patch(READER)
    def test_file_name_date_is_utc(
        self,
        mock_reader,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
        local_zone: str,
        file_name: str,
        expected: datetime,
    ) -> None:
        mock_reader.get_creation_datetime.return_value = EARLIER_FILE_SYSTEM_DATE
        mock_reader.get_first_commit_datetime.return_value = EARLIER_FILE_SYSTEM_DATE
        monkeypatch.setenv("TZ", local_zone)
        time.tzset()
        try:
            assert expected.replace(tzinfo=None).astimezone().utcoffset() != timedelta(0)
            f = tmp_path / file_name
            f.touch()

            result = _get_date_from_file(f)

            assert result == expected
            assert result.tzinfo == timezone.utc
            assert result.utcoffset() == timedelta(0)
            assert f"{result:%Y%m%d%H%M%S}" == f"{expected:%Y%m%d%H%M%S}"
            mock_reader.get_creation_datetime.assert_not_called()
            mock_reader.get_first_commit_datetime.assert_not_called()
        finally:
            monkeypatch.undo()
            time.tzset()

    @pytest.mark.parametrize(
        ("file_name", "expected"),
        [
            ("20240115143060 note.md", datetime(2024, 1, 15, 14, 30, 59, tzinfo=timezone.utc)),
            ("20240115143075 note.md", datetime(2024, 1, 15, 14, 30, 59, tzinfo=timezone.utc)),
            ("20240115143099 note.md", datetime(2024, 1, 15, 14, 30, 59, tzinfo=timezone.utc)),
            ("20231231235999.md", datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
            ("20240115143059 note.md", datetime(2024, 1, 15, 14, 30, 59, tzinfo=timezone.utc)),
            ("20240115143058 note.md", datetime(2024, 1, 15, 14, 30, 58, tzinfo=timezone.utc)),
            ("20240115143000 note.md", datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)),
        ],
        ids=["60", "75", "99", "99-does-not-roll-into-next-year", "59-stays", "58-unchanged", "00-unchanged"],
    )
    @patch(READER)
    def test_suffix_seconds_map_to_59(self, mock_reader, tmp_path, file_name: str, expected: datetime) -> None:
        mock_reader.get_creation_datetime.return_value = EARLIER_FILE_SYSTEM_DATE
        mock_reader.get_first_commit_datetime.return_value = EARLIER_FILE_SYSTEM_DATE
        f = tmp_path / file_name
        f.touch()

        result = _get_date_from_file(f)

        assert result == expected
        assert result.tzinfo == timezone.utc
        assert f"{result:%Y%m%d%H%M%S}" == f"{expected:%Y%m%d%H%M%S}"
        mock_reader.get_creation_datetime.assert_not_called()
        mock_reader.get_first_commit_datetime.assert_not_called()

    @pytest.mark.parametrize(
        ("creation", "first_commit", "expected"),
        [
            (
                datetime(2024, 3, 1, 9, tzinfo=timezone.utc),
                datetime(2023, 5, 2, 10, tzinfo=timezone.utc),
                datetime(2023, 5, 2, 10, tzinfo=timezone.utc),
            ),
            (
                datetime(2022, 8, 9, 7, tzinfo=timezone.utc),
                datetime(2023, 5, 2, 10, tzinfo=timezone.utc),
                datetime(2022, 8, 9, 7, tzinfo=timezone.utc),
            ),
            (None, datetime(2023, 5, 2, 10, tzinfo=timezone.utc), datetime(2023, 5, 2, 10, tzinfo=timezone.utc)),
        ],
        ids=["commit-earlier", "creation-earlier", "no-creation-date"],
    )
    @pytest.mark.parametrize("file_name", ["20241315143022 note.md", "202413151430 note.md"], ids=["14", "12"])
    @patch(READER)
    def test_invalid_file_name_date_falls_back_to_earliest_file_date(
        self, mock_reader, tmp_path, file_name: str, creation, first_commit, expected: datetime
    ) -> None:
        mock_reader.get_creation_datetime.return_value = creation
        mock_reader.get_first_commit_datetime.return_value = first_commit
        f = tmp_path / file_name
        f.touch()

        result = _get_date_from_file(f)

        assert result == expected
        mock_reader.get_creation_datetime.assert_called_once_with(f)
        mock_reader.get_first_commit_datetime.assert_called_once_with(f)
