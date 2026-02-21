from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from netscan.cli import cli


class TestNetscanCommands:
    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_hosts_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Found 3 hosts")
        runner = CliRunner()
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert result.exit_code == 0

    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_ssh_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="Found 2 SSH hosts")
        runner = CliRunner()
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert result.exit_code == 0
