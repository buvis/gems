from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult, FatalError
from click.testing import CliRunner
from puc.cli import cli


class TestPucStripCli:
    @patch("puc.commands.strip.strip.CommandStrip")
    def test_strip_failure(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.write_bytes(b"\xff\xd8\xff")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="exiftool missing")
        runner = CliRunner()
        result = runner.invoke(cli, ["strip", str(photo)])
        assert result.exit_code == 0

    @patch("puc.commands.strip.strip.CommandStrip")
    def test_strip_failure_no_error(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.write_bytes(b"\xff\xd8\xff")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["strip", str(photo)])
        assert result.exit_code == 0

    @patch("puc.commands.strip.strip.CommandStrip")
    def test_strip_success_no_output(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.write_bytes(b"\xff\xd8\xff")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["strip", str(photo)])
        assert result.exit_code == 0

    @patch("puc.commands.strip.strip.CommandStrip")
    def test_strip_with_warnings(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.write_bytes(b"\xff\xd8\xff")
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Stripped 1", warnings=["corrupt exif in test.jpg"]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["strip", str(photo)])
        assert result.exit_code == 0

    @patch("puc.commands.strip.strip.CommandStrip")
    def test_strip_fatal_error(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        photo = tmp_path / "test.jpg"
        photo.write_bytes(b"\xff\xd8\xff")
        mock_cmd_cls.return_value.execute.side_effect = FatalError("exiftool not found")
        runner = CliRunner()
        result = runner.invoke(cli, ["strip", str(photo)])
        assert "exiftool not found" in result.output
