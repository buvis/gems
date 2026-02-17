from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from buvis.pybase.filesystem import FileMetadataReader

PLATFORM_SYSTEM_PATH = "buvis.pybase.filesystem.file_metadata.file_metadata_reader.platform.system"
TZLOCAL_GET_LOCALZONE_PATH = "buvis.pybase.filesystem.file_metadata.file_metadata_reader.tzlocal.get_localzone"


def _make_stat_result(**attrs: float) -> MagicMock:
    stat = MagicMock(spec_set=tuple(attrs.keys()))
    for name, value in attrs.items():
        setattr(stat, name, value)
    return stat


class TestGetCreationDatetime:
    """Tests for FileMetadataReader.get_creation_datetime."""

    def test_uses_st_ctime_on_windows(self, tmp_path: Path) -> None:
        file = tmp_path / "test.txt"
        file.touch()
        creation_timestamp = 1_700_000_000.0
        stat_result = _make_stat_result(st_ctime=creation_timestamp)

        with (
            patch(PLATFORM_SYSTEM_PATH, return_value="Windows"),
            patch(TZLOCAL_GET_LOCALZONE_PATH, return_value=timezone.utc),
            patch.object(type(file), "stat", return_value=stat_result) as mock_stat,
        ):
            result = FileMetadataReader.get_creation_datetime(file)

        mock_stat.assert_called_once_with()
        assert result == datetime.fromtimestamp(creation_timestamp, tz=timezone.utc)

    def test_uses_st_birthtime_on_macos(self, tmp_path: Path) -> None:
        file = tmp_path / "test.txt"
        file.touch()
        birth_timestamp = 1_600_000_000.0
        stat_result = _make_stat_result(st_birthtime=birth_timestamp)

        with (
            patch(PLATFORM_SYSTEM_PATH, return_value="Darwin"),
            patch(TZLOCAL_GET_LOCALZONE_PATH, return_value=timezone.utc),
            patch.object(type(file), "stat", return_value=stat_result) as mock_stat,
        ):
            result = FileMetadataReader.get_creation_datetime(file)

        mock_stat.assert_called_once_with()
        assert result == datetime.fromtimestamp(birth_timestamp, tz=timezone.utc)

    def test_falls_back_to_st_mtime_when_no_birthtime(self, tmp_path: Path) -> None:
        """Linux doesn't have st_birthtime, falls back to st_mtime."""
        file = tmp_path / "test.txt"
        file.touch()
        fallback_timestamp = 1_500_000_000.0
        stat_result = _make_stat_result(st_mtime=fallback_timestamp)

        with (
            patch(PLATFORM_SYSTEM_PATH, return_value="Linux"),
            patch(TZLOCAL_GET_LOCALZONE_PATH, return_value=timezone.utc),
            patch.object(type(file), "stat", return_value=stat_result) as mock_stat,
        ):
            result = FileMetadataReader.get_creation_datetime(file)

        mock_stat.assert_called_once_with()
        assert result == datetime.fromtimestamp(fallback_timestamp, tz=timezone.utc)


class TestGetFirstCommitDatetime:
    """Tests for FileMetadataReader.get_first_commit_datetime."""

    @patch("buvis.pybase.filesystem.file_metadata.file_metadata_reader.subprocess.check_output")
    def test_parses_git_log_output(self, mock_check_output: Mock, tmp_path: Path) -> None:
        mock_check_output.return_value = "2024-01-15T10:30:00+0000\n"
        result = FileMetadataReader.get_first_commit_datetime(tmp_path / "file.txt")
        assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    @pytest.mark.parametrize("offset", ["+0530", "-0800"])
    @patch("buvis.pybase.filesystem.file_metadata.file_metadata_reader.subprocess.check_output")
    def test_parses_git_log_output_with_timezone_offsets(
        self, mock_check_output: Mock, tmp_path: Path, offset: str
    ) -> None:
        date_line = f"2024-01-15T10:30:00{offset}\n"
        mock_check_output.return_value = date_line
        expected = datetime.strptime(date_line.strip(), "%Y-%m-%dT%H:%M:%S%z")

        result = FileMetadataReader.get_first_commit_datetime(tmp_path / "file.txt")

        assert result == expected
        assert result.tzinfo == expected.tzinfo

    @patch("buvis.pybase.filesystem.file_metadata.file_metadata_reader.subprocess.check_output")
    def test_returns_none_when_not_in_git_repo(self, mock_check_output: Mock, tmp_path: Path) -> None:
        mock_check_output.side_effect = subprocess.CalledProcessError(128, "git")
        result = FileMetadataReader.get_first_commit_datetime(tmp_path / "file.txt")
        assert result is None

    @patch("buvis.pybase.filesystem.file_metadata.file_metadata_reader.subprocess.check_output")
    def test_returns_none_for_uncommitted_file(self, mock_check_output: Mock, tmp_path: Path) -> None:
        mock_check_output.return_value = ""
        result = FileMetadataReader.get_first_commit_datetime(tmp_path / "file.txt")
        assert result is None

    @patch("buvis.pybase.filesystem.file_metadata.file_metadata_reader.subprocess.check_output")
    def test_returns_none_for_malformed_date(self, mock_check_output: Mock, tmp_path: Path) -> None:
        mock_check_output.return_value = "not-a-date\n"
        result = FileMetadataReader.get_first_commit_datetime(tmp_path / "file.txt")
        assert result is None
