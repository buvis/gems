from unittest.mock import patch

import pytest
from zseq.commands import CommandGetLast


class TestCommandGetLast:
    def test_raises_on_invalid_dir(self, tmp_path):
        with pytest.raises(ValueError, match="is not a directory"):
            CommandGetLast(
                path_dir=str(tmp_path / "nonexistent"),
                is_reporting_misnamed=False,
            )

    @patch("zseq.commands.get_last.get_last.console")
    def test_finds_max_seq(self, mock_console, tmp_path):
        (tmp_path / "20240114122450-0010-first.md").touch()
        (tmp_path / "20240114122450-0050-second.md").touch()
        (tmp_path / "20240114122450-0030-third.md").touch()

        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        cmd.execute()

        mock_console.success.assert_called_once()
        call_msg = mock_console.success.call_args[0][0]
        assert "50" in call_msg

    @patch("zseq.commands.get_last.get_last.console")
    def test_no_zettelseq_files(self, mock_console, tmp_path):
        (tmp_path / "random-file.txt").touch()
        (tmp_path / "another.md").touch()

        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        cmd.execute()

        mock_console.failure.assert_called_once()
        call_msg = mock_console.failure.call_args[0][0]
        assert "No files" in call_msg

    @patch("zseq.commands.get_last.get_last.console")
    def test_skips_directories(self, mock_console, tmp_path):
        (tmp_path / "20240114122450-0010-first.md").touch()
        (tmp_path / "20240114122450-0099-subdir").mkdir()

        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        cmd.execute()

        mock_console.success.assert_called_once()
        call_msg = mock_console.success.call_args[0][0]
        assert "10" in call_msg

    @patch("zseq.commands.get_last.get_last.console")
    def test_empty_dir(self, mock_console, tmp_path):
        cmd = CommandGetLast(path_dir=str(tmp_path), is_reporting_misnamed=False)
        cmd.execute()

        mock_console.failure.assert_called_once()
