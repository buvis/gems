from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from muc.cli import cli


class TestMucLimitCli:
    @patch("muc.commands.limit.limit.CommandLimit")
    def test_limit_success(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Transcoded 5 files")
        result = runner.invoke(cli, ["limit", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.limit.limit.CommandLimit")
    def test_limit_failure(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="ffmpeg missing")
        result = runner.invoke(cli, ["limit", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.limit.limit.CommandLimit")
    def test_limit_failure_no_error(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        result = runner.invoke(cli, ["limit", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.limit.limit.CommandLimit")
    def test_limit_success_no_output(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["limit", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.limit.limit.CommandLimit")
    def test_limit_with_warnings(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Transcoded 2", warnings=["skipped corrupt.flac"]
        )
        result = runner.invoke(cli, ["limit", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.limit.limit.CommandLimit")
    def test_limit_with_output_dir(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        out = tmp_path / "out"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Done")
        result = runner.invoke(cli, ["limit", "-o", str(out), str(tmp_path)])
        assert result.exit_code == 0

    def test_limit_not_a_dir(self, runner, tmp_path) -> None:
        result = runner.invoke(cli, ["limit", str(tmp_path / "nope")])
        assert result.exit_code != 0 or "isn't a directory" in result.output

    def test_limit_import_error(self, runner, tmp_path) -> None:
        mod_key = "muc.commands.limit.limit"
        saved = sys.modules.pop(mod_key, None)
        try:
            with patch.dict(sys.modules, {mod_key: None}):
                result = runner.invoke(cli, ["limit", str(tmp_path)])
                assert "muc" in result.output
        finally:
            if saved is not None:
                sys.modules[mod_key] = saved


class TestMucCoverCliExtra:
    @patch("muc.commands.cover.cover.CommandCover")
    def test_cover_success_no_output(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["cover", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.cover.cover.CommandCover")
    def test_cover_failure_no_error(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        result = runner.invoke(cli, ["cover", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.cover.cover.CommandCover")
    def test_cover_with_warnings(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Cleaned 1", warnings=["skipped dir"]
        )
        result = runner.invoke(cli, ["cover", str(tmp_path)])
        assert result.exit_code == 0


class TestMucTidyCliExtra:
    @patch("muc.commands.tidy.tidy.CommandTidy")
    @patch("buvis.pybase.filesystem.DirTree")
    def test_tidy_large_dir_confirmed(self, mock_dirtree: MagicMock, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_dirtree.count_files.return_value = 200
        mock_dirtree.get_max_depth.return_value = 5
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["tidy", str(tmp_path)], input="y\n")
        assert result.exit_code == 0

    @patch("buvis.pybase.filesystem.DirTree")
    def test_tidy_large_dir_aborted(self, mock_dirtree: MagicMock, runner, tmp_path) -> None:
        mock_dirtree.count_files.return_value = 200
        mock_dirtree.get_max_depth.return_value = 5
        result = runner.invoke(cli, ["tidy", str(tmp_path)], input="n\n")
        assert result.exit_code == 0  # declined, early return
