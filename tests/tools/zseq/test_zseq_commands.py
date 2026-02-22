from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from zseq.cli import cli


class TestZseqCommands:
    @patch("zseq.commands.get_last.get_last.CommandGetLast")
    def test_get_last_success(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="2024-0042")
        runner = CliRunner()
        result = runner.invoke(cli, ["--path", str(tmp_path)])
        assert result.exit_code == 0

    @patch("zseq.commands.get_last.get_last.CommandGetLast")
    def test_get_last_with_misnamed(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True,
            output="2024-0042",
            warnings=["bad.txt is misnamed"],
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--path", str(tmp_path), "--misnamed-reporting"])
        assert result.exit_code == 0

    @patch("zseq.commands.get_last.get_last.CommandGetLast")
    def test_get_last_failure(self, mock_cmd_cls: MagicMock, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="no files found")
        runner = CliRunner()
        result = runner.invoke(cli, ["--path", str(tmp_path)])
        assert result.exit_code == 0  # CLI prints failure but doesn't sys.exit
