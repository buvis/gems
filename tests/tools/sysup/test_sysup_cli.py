from __future__ import annotations

from unittest.mock import MagicMock, patch

import click

from sysup.cli import cli
from sysup.commands.step_result import StepResult


class TestSysupCli:
    def test_cli_group_exists(self) -> None:
        assert isinstance(cli, click.Group)

    def test_mac_command_exists(self) -> None:
        assert "mac" in cli.commands

    def test_pip_command_exists(self) -> None:
        assert "pip" in cli.commands

    def test_wsl_command_exists(self) -> None:
        assert "wsl" in cli.commands


class TestSysupCliHelp:
    def test_help(self, runner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "mac" in result.output
        assert "pip" in result.output
        assert "wsl" in result.output

    def test_mac_help(self, runner) -> None:
        result = runner.invoke(cli, ["mac", "--help"])
        assert result.exit_code == 0

    def test_pip_help(self, runner) -> None:
        result = runner.invoke(cli, ["pip", "--help"])
        assert result.exit_code == 0

    def test_wsl_help(self, runner) -> None:
        result = runner.invoke(cli, ["wsl", "--help"])
        assert result.exit_code == 0


class TestSysupMacCommand:
    @patch("sysup.cli.sys")
    @patch("sysup.commands.mac.mac.CommandMac")
    def test_mac_success(self, mock_cmd_cls: MagicMock, mock_sys: MagicMock, runner) -> None:
        mock_sys.platform = "darwin"
        mock_cmd_cls.return_value.execute.return_value = [
            StepResult("brew", True, "brew updated"),
        ]
        result = runner.invoke(cli, ["mac"])
        assert result.exit_code == 0


class TestSysupPipCommand:
    @patch("sysup.commands.pip.pip.CommandPip")
    def test_pip_success(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = [
            StepResult("pip", True, "pip upgraded"),
        ]
        result = runner.invoke(cli, ["pip"])
        assert result.exit_code == 0

    @patch("sysup.commands.pip.pip.CommandPip")
    def test_pip_failure_step(self, mock_cmd_cls: MagicMock, runner) -> None:
        mock_cmd_cls.return_value.execute.return_value = [
            StepResult("pip", False, "pip update failed"),
        ]
        result = runner.invoke(cli, ["pip"])
        assert result.exit_code == 0


class TestSysupWslCommand:
    @patch("sysup.cli.sys")
    def test_wsl_wrong_platform(self, mock_sys: MagicMock, runner) -> None:
        mock_sys.platform = "darwin"
        result = runner.invoke(cli, ["wsl"])
        assert "only available on Linux" in result.output

    @patch("sysup.commands.wsl.wsl.CommandWsl")
    @patch("sysup.cli.sys")
    def test_wsl_success(self, mock_sys: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        mock_sys.platform = "linux"
        mock_cmd_cls.return_value.execute.return_value = [
            StepResult("apt", True, "apt updated"),
        ]
        result = runner.invoke(cli, ["wsl"])
        assert result.exit_code == 0

    @patch("sysup.commands.wsl.wsl.CommandWsl")
    @patch("sysup.cli.sys")
    def test_wsl_fatal_error(self, mock_sys: MagicMock, mock_cmd_cls: MagicMock, runner) -> None:
        from buvis.pybase.result import FatalError

        mock_sys.platform = "linux"
        mock_cmd_cls.return_value.execute.side_effect = FatalError("sudo required")
        result = runner.invoke(cli, ["wsl"])
        assert "sudo required" in result.output


class TestSysupMacCommandExtra:
    @patch("sysup.cli.sys")
    @patch("sysup.commands.mac.mac.CommandMac")
    def test_mac_fatal_error(self, mock_cmd_cls: MagicMock, mock_sys: MagicMock, runner) -> None:
        from buvis.pybase.result import FatalError

        mock_sys.platform = "darwin"
        mock_cmd_cls.return_value.execute.side_effect = FatalError("xcode missing")
        result = runner.invoke(cli, ["mac"])
        assert "xcode missing" in result.output

    @patch("sysup.cli.sys")
    @patch("sysup.commands.mac.mac.CommandMac")
    def test_mac_report_steps_default_messages(self, mock_cmd_cls: MagicMock, mock_sys: MagicMock, runner) -> None:
        mock_sys.platform = "darwin"
        mock_cmd_cls.return_value.execute.return_value = [
            StepResult("brew", True),
            StepResult("mas", False),
        ]
        result = runner.invoke(cli, ["mac"])
        assert result.exit_code == 0
