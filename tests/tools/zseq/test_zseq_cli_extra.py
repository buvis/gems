from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult, FatalError
from zseq.cli import cli


class TestZseqCliExtra:
    @patch("zseq.commands.get_last.get_last.CommandGetLast")
    def test_get_last_failure_no_error(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        result = runner.invoke(cli, ["--path", str(tmp_path)])
        assert result.exit_code == 0

    @patch("zseq.commands.get_last.get_last.CommandGetLast")
    def test_get_last_success_no_output(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["--path", str(tmp_path)])
        assert result.exit_code == 0

    @patch("zseq.commands.get_last.get_last.CommandGetLast")
    def test_get_last_fatal_error(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.side_effect = FatalError("path missing")
        result = runner.invoke(cli, ["--path", str(tmp_path)])
        assert "path missing" in result.output

    @patch("zseq.commands.get_last.get_last.CommandGetLast")
    def test_get_last_value_error(self, mock_cmd_cls: MagicMock, runner, tmp_path) -> None:
        mock_cmd_cls.return_value.execute.side_effect = ValueError("bad path")
        result = runner.invoke(cli, ["--path", str(tmp_path)])
        assert "bad path" in result.output
