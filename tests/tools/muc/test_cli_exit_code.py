from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from muc.cli import cli


class TestLimitExitCode:
    @patch("muc.commands.limit.limit.CommandLimit")
    def test_exits_nonzero_when_result_fails(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="ffmpeg missing")
        result = runner.invoke(cli, ["limit", str(tmp_path)])
        assert result.exit_code != 0
        assert "ffmpeg missing" in result.output

    @patch("muc.commands.limit.limit.CommandLimit")
    def test_exits_zero_when_result_succeeds(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Transcoded 5 files")
        result = runner.invoke(cli, ["limit", str(tmp_path)])
        assert result.exit_code == 0


class TestCoverExitCode:
    @patch("muc.commands.cover.cover.CommandCover")
    def test_exits_nonzero_when_result_fails(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="cover scan failed")
        result = runner.invoke(cli, ["cover", str(tmp_path)])
        assert result.exit_code != 0
        assert "cover scan failed" in result.output

    @patch("muc.commands.cover.cover.CommandCover")
    def test_exits_zero_when_result_succeeds(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="No duplicate covers found")
        result = runner.invoke(cli, ["cover", str(tmp_path)])
        assert result.exit_code == 0


class TestTidyAggregateExitCode:
    """Only the aggregate report_result call after the per-step loop (~line 90).

    The per-step loop itself (~line 89) is excluded by design: it stays
    exit-0 regardless of each step's success, per the dispatch task.
    """

    @patch("muc.commands.tidy.tidy.CommandTidy")
    @patch("muc.shared.dir_tree.DirTree")
    def test_exits_nonzero_when_aggregate_result_fails(
        self, mock_dirtree: MagicMock, mock_cmd_cls: MagicMock, runner, tmp_path
    ) -> None:
        mock_dirtree.count_files.return_value = 1
        mock_dirtree.get_max_depth.return_value = 1
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=False,
            error="tidy failed",
            metadata={"steps": [CommandResult(success=True, output="merged mac metadata")]},
        )
        result = runner.invoke(cli, ["tidy", str(tmp_path)])
        assert result.exit_code != 0
        assert "tidy failed" in result.output

    @patch("muc.commands.tidy.tidy.CommandTidy")
    @patch("muc.shared.dir_tree.DirTree")
    def test_exits_zero_when_aggregate_result_succeeds(
        self, mock_dirtree: MagicMock, mock_cmd_cls: MagicMock, runner, tmp_path
    ) -> None:
        mock_dirtree.count_files.return_value = 1
        mock_dirtree.get_max_depth.return_value = 1
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="tidy done",
            metadata={"steps": [CommandResult(success=False, error="step warned but tidy keeps going")]},
        )
        result = runner.invoke(cli, ["tidy", str(tmp_path)])
        assert result.exit_code == 0
