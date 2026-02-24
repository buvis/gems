from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult, FatalError
from outlookctl.cli import cli


class TestOutlookctlCreateTimeblock:
    @patch("outlookctl.commands.create_timeblock.create_timeblock.CommandCreateTimeblock")
    @patch("outlookctl.cli.os")
    def test_create_timeblock_success(self, mock_os: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        mock_os.name = "nt"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Created block 14:00-14:25")
        result = runner.invoke(cli, ["create_timeblock"])
        assert result.exit_code == 0

    @patch("outlookctl.commands.create_timeblock.create_timeblock.CommandCreateTimeblock")
    @patch("outlookctl.cli.os")
    def test_create_timeblock_failure(self, mock_os: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        mock_os.name = "nt"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="calendar busy")
        result = runner.invoke(cli, ["create_timeblock"])
        assert result.exit_code == 0

    @patch("outlookctl.commands.create_timeblock.create_timeblock.CommandCreateTimeblock")
    @patch("outlookctl.cli.os")
    def test_create_timeblock_failure_no_error(self, mock_os: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        mock_os.name = "nt"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        result = runner.invoke(cli, ["create_timeblock"])
        assert result.exit_code == 0

    @patch("outlookctl.commands.create_timeblock.create_timeblock.CommandCreateTimeblock")
    @patch("outlookctl.cli.os")
    def test_create_timeblock_fatal_error(self, mock_os: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        mock_os.name = "nt"
        mock_cmd_cls.return_value.execute.side_effect = FatalError("COM init failed")
        result = runner.invoke(cli, ["create_timeblock"])
        assert "COM init failed" in result.output

    @patch("outlookctl.commands.create_timeblock.create_timeblock.CommandCreateTimeblock")
    @patch("outlookctl.cli.os")
    def test_create_timeblock_success_no_output(self, mock_os: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        mock_os.name = "nt"
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        result = runner.invoke(cli, ["create_timeblock"])
        assert result.exit_code == 0
