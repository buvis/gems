"""Exit-code contract for the ``klyreon schedule`` subcommands' terminal
``console.report_result`` call: install, status, uninstall.
"""

from __future__ import annotations

from types import SimpleNamespace

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from klyreon.cli import cli


class TestScheduleInstallExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=False, error="schedule install failed")
        mocker.patch(
            "klyreon.commands.schedule.CommandScheduleInstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["schedule", "install"])

        assert result.exit_code != 0
        assert "schedule install failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=True, output="schedule installed")
        mocker.patch(
            "klyreon.commands.schedule.CommandScheduleInstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["schedule", "install"])

        assert result.exit_code == 0


class TestScheduleStatusExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=False, error="schedule status failed")
        mocker.patch(
            "klyreon.commands.schedule.CommandScheduleStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["schedule", "status"])

        assert result.exit_code != 0
        assert "schedule status failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=True, output="schedule present")
        mocker.patch(
            "klyreon.commands.schedule.CommandScheduleStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["schedule", "status"])

        assert result.exit_code == 0


class TestScheduleUninstallExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=False, error="schedule uninstall failed")
        mocker.patch(
            "klyreon.commands.schedule.CommandScheduleUninstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["schedule", "uninstall"])

        assert result.exit_code != 0
        assert "schedule uninstall failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=True, output="schedule removed")
        mocker.patch(
            "klyreon.commands.schedule.CommandScheduleUninstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["schedule", "uninstall"])

        assert result.exit_code == 0
