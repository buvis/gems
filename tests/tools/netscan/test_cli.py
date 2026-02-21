from __future__ import annotations

from click.testing import CliRunner
from netscan.cli import cli


class TestNetscanCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "hosts" in result.output
        assert "ssh" in result.output

    def test_hosts_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["hosts", "--help"])
        assert result.exit_code == 0
        assert "--interface" in result.output

    def test_ssh_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["ssh", "--help"])
        assert result.exit_code == 0
        assert "--interface" in result.output
        assert "--port" in result.output
