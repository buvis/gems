from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from sysup.cli import cli
from sysup.commands.step_result import StepResult


class TestSysupCliHelp:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "mac" in result.output
        assert "pip" in result.output
        assert "wsl" in result.output

    def test_mac_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["mac", "--help"])
        assert result.exit_code == 0

    def test_pip_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["pip", "--help"])
        assert result.exit_code == 0

    def test_wsl_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["wsl", "--help"])
        assert result.exit_code == 0


class TestSysupMacCommand:
    @patch("sysup.commands.mac.mac.CommandMac")
    def test_mac_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = [
            StepResult("brew", True, "brew updated"),
        ]
        runner = CliRunner()
        result = runner.invoke(cli, ["mac"])
        assert result.exit_code == 0


class TestSysupPipCommand:
    @patch("sysup.commands.pip.pip.CommandPip")
    def test_pip_success(self, mock_cmd_cls: MagicMock) -> None:
        mock_cmd_cls.return_value.execute.return_value = [
            StepResult("pip", True, "pip upgraded"),
        ]
        runner = CliRunner()
        result = runner.invoke(cli, ["pip"])
        assert result.exit_code == 0
