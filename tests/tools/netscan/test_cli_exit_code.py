from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from netscan.cli import cli


class TestHostsExitCode:
    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_exits_nonzero_when_result_fails(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="no interface")
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert result.exit_code != 0
        assert "no interface" in result.output

    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_exits_zero_when_result_succeeds(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Found 3 hosts")
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert result.exit_code == 0


class TestSshExitCode:
    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_exits_nonzero_when_result_fails(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="port closed")
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert result.exit_code != 0
        assert "port closed" in result.output

    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_exits_zero_when_result_succeeds(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Found 2 SSH hosts")
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert result.exit_code == 0
