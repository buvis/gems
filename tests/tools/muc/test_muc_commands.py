from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from muc.cli import cli


class TestMucCommands:
    @patch("muc.commands.cover.cover.CommandCover")
    def test_cover_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Cleaned 3 dirs")
        runner = CliRunner()
        result = runner.invoke(cli, ["cover", str(tmp_path)])
        assert result.exit_code == 0

    @patch("muc.commands.cover.cover.CommandCover")
    def test_cover_failure(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="no covers found")
        runner = CliRunner()
        result = runner.invoke(cli, ["cover", str(tmp_path)])
        assert result.exit_code == 0  # CLI prints failure but doesn't sys.exit

    def test_cover_not_a_dir(self, tmp_path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["cover", str(tmp_path / "nope")])
        assert result.exit_code != 0 or "isn't a directory" in result.output

    @patch("muc.commands.tidy.tidy.CommandTidy")
    @patch("muc.cli.DirTree")
    def test_tidy_success(self, mock_dirtree: MagicMock, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_dirtree.count_files.return_value = 5
        mock_dirtree.get_max_depth.return_value = 1
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Tidied")
        runner = CliRunner()
        result = runner.invoke(cli, ["tidy", "-y", str(tmp_path)])
        assert result.exit_code == 0

    def test_tidy_not_a_dir(self, tmp_path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tidy", str(tmp_path / "nope")])
        assert result.exit_code != 0 or "isn't a directory" in result.output
