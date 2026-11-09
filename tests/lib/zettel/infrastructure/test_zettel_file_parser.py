from datetime import datetime
from unittest.mock import patch

from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
    _get_date_from_file,
)


class TestGetDateFromFile:
    @patch("buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser.FileMetadataReader")
    def test_14_digit_filename_is_local_wall_clock(self, mock_reader, tmp_path):
        """The 14 digits are the local-time id, so the date keeps them as local wall-clock time."""
        f = tmp_path / "20240115143022 some note.md"
        f.touch()

        result = _get_date_from_file(f)

        assert result == datetime(2024, 1, 15, 14, 30, 22).astimezone()
        assert result.tzinfo is not None
        assert f"{result:%Y%m%d%H%M%S}" == "20240115143022"

    @patch("buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser.FileMetadataReader")
    def test_12_digit_filename_is_local_wall_clock(self, mock_reader, tmp_path):
        """Filename with 12-digit timestamp (YYYYMMDDHHmm) should parse correctly."""
        f = tmp_path / "202401151430 some note.md"
        f.touch()

        result = _get_date_from_file(f)

        assert result == datetime(2024, 1, 15, 14, 30).astimezone()
        assert f"{result:%Y%m%d%H%M}" == "202401151430"
