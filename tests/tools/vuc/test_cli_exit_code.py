from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from vuc.cli import cli


class TestMultilangExitCode:
    @patch("vuc.commands.multilang.CommandMultilang")
    @patch("vuc.cli.shutil")
    def test_exits_nonzero_when_result_fails(
        self, mock_shutil: MagicMock, mock_cmd_cls: MagicMock, runner, tmp_path
    ) -> None:
        mock_shutil.which.return_value = "/usr/bin/mediainfo"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="bad format")
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert result.exit_code != 0
        assert "bad format" in result.output

    @patch("vuc.commands.multilang.CommandMultilang")
    @patch("vuc.cli.shutil")
    def test_exits_zero_when_result_succeeds(
        self, mock_shutil: MagicMock, mock_cmd_cls: MagicMock, runner, tmp_path
    ) -> None:
        mock_shutil.which.return_value = "/usr/bin/mediainfo"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Found 2 multilang videos")
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert result.exit_code == 0
