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
        output = " ".join(result.output.split())
        assert result.exit_code != 0 or "isn't a directory" in output

    @patch("vuc.cli.shutil")
    def test_multilang_no_mediainfo(self, mock_shutil: MagicMock, tmp_path) -> None:
        mock_shutil.which.return_value = None
        runner = CliRunner()
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert "mediainfo is required" in result.output

    @patch("vuc.commands.multilang.CommandMultilang")
    @patch("vuc.cli.shutil")
    def test_multilang_failure(self, mock_shutil: MagicMock, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_shutil.which.return_value = "/usr/bin/mediainfo"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="bad format")
        runner = CliRunner()
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert result.exit_code == 0

    @patch("vuc.commands.multilang.CommandMultilang")
    @patch("vuc.cli.shutil")
    def test_multilang_failure_no_error(self, mock_shutil: MagicMock, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_shutil.which.return_value = "/usr/bin/mediainfo"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert result.exit_code == 0

    @patch("vuc.commands.multilang.CommandMultilang")
    @patch("vuc.cli.shutil")
    def test_multilang_success_no_output(self, mock_shutil: MagicMock, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_shutil.which.return_value = "/usr/bin/mediainfo"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert result.exit_code == 0

    @patch("vuc.commands.multilang.CommandMultilang")
    @patch("vuc.cli.shutil")
    def test_multilang_with_warnings(self, mock_shutil: MagicMock, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_shutil.which.return_value = "/usr/bin/mediainfo"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Found 1", warnings=["skipped corrupt.mkv"]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["multilang", str(tmp_path), str(tmp_path / "out.csv")])
        assert result.exit_code == 0
