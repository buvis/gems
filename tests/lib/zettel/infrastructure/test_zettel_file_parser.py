from datetime import datetime, timezone
from unittest.mock import patch

from buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser import (
    _get_date_from_file,
)


class TestGetDateFromFile:
    @patch("buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser.FileMetadataReader")
    def test_14_digit_filename(self, mock_reader, tmp_path):
        """Filename with 14-digit timestamp (YYYYMMDDHHmmSS) should parse correctly."""
        f = tmp_path / "20240115143022 some note.md"
        f.touch()

        result = _get_date_from_file(f)

        assert result == datetime(2024, 1, 15, 14, 30, 22, tzinfo=timezone.utc)

    @patch("buvis.pybase.zettel.infrastructure.persistence.file_parsers.zettel_file_parser.FileMetadataReader")
    def test_12_digit_filename(self, mock_reader, tmp_path):
        """Filename with 12-digit timestamp (YYYYMMDDHHmm) should parse correctly."""
        f = tmp_path / "202401151430 some note.md"
        f.touch()

        result = _get_date_from_file(f)

        assert result == datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc)
