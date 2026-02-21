from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from vuc.cli import cli


class TestVucCommands:
    @patch("vuc.commands.multilang.CommandMultilang")
    @patch("vuc.cli.shutil")
    def test_multilang_success(self, mock_shutil: MagicMock, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_shutil.which.return_value = "/usr/bin/mediainfo"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Found 2 multilang videos")
        runner = CliRunner()
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert result.exit_code == 0

    def test_multilang_not_a_dir(self, tmp_path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["multilang", str(tmp_path / "nope"), str(tmp_path / "out.csv")])
        assert result.exit_code != 0 or "isn't a directory" in result.output
