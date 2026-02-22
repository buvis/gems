from __future__ import annotations

from unittest.mock import MagicMock, patch

from buvis.pybase.result import CommandResult, FatalError
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

    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_hosts_failure(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="no interface")
        runner = CliRunner()
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert result.exit_code == 0

    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_hosts_failure_no_error(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert result.exit_code == 0

    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_hosts_success_no_output(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert result.exit_code == 0

    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_hosts_with_warnings(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Found 1", warnings=["timeout on 10.0.0.5"]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert result.exit_code == 0

    @patch("netscan.commands.hosts.hosts.CommandHosts")
    def test_hosts_fatal_error(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.side_effect = FatalError("nmap not found")
        runner = CliRunner()
        result = runner.invoke(cli, ["hosts", "-i", "en0"])
        assert "nmap not found" in result.output

    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_ssh_failure(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False, error="port closed")
        runner = CliRunner()
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert result.exit_code == 0

    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_ssh_failure_no_error(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert result.exit_code == 0

    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_ssh_success_no_output(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True)
        runner = CliRunner()
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert result.exit_code == 0

    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_ssh_with_warnings(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = CommandResult(
            success=True, output="Found 1", warnings=["slow response from 10.0.0.2"]
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert result.exit_code == 0

    @patch("netscan.commands.ssh.ssh.CommandSsh")
    def test_ssh_fatal_error(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.side_effect = FatalError("nmap not found")
        runner = CliRunner()
        result = runner.invoke(cli, ["ssh", "-i", "en0", "-p", "22"])
        assert "nmap not found" in result.output
