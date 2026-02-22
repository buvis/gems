from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from pinger.cli import cli


class TestPingerCommands:
    @patch("pinger.commands.wait.wait.CommandWait")
    def test_wait_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="ok")
        runner = CliRunner()
        result = runner.invoke(cli, ["wait", "192.168.1.1"])
        assert result.exit_code == 0
        assert "online" in result.output

    @patch("pinger.commands.wait.wait.CommandWait")
    def test_wait_with_timeout(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="ok")
        runner = CliRunner()
        result = runner.invoke(cli, ["wait", "-t", "10", "example.com"])
        assert result.exit_code == 0

    @patch("pinger.commands.wait.exceptions.CommandWaitTimeoutError", Exception)
    @patch("pinger.commands.wait.wait.CommandWait")
    def test_wait_timeout(self, mock_cmd_cls: MagicMock) -> None:
        from pinger.commands.wait.exceptions import CommandWaitTimeoutError

        mock_cmd_cls.return_value.execute.side_effect = CommandWaitTimeoutError
        runner = CliRunner()
        result = runner.invoke(cli, ["wait", "10.0.0.1"])
        assert result.exit_code != 0 or "Timeout" in result.output
