"""Exit-code contract for the ``klyreon assets`` subcommands' terminal
``console.report_result`` call: install, status, refresh, uninstall.
"""

from __future__ import annotations

from types import SimpleNamespace

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from klyreon.cli import cli


class TestAssetsInstallExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=False, error="assets install failed")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsInstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "install", "--operator", "claude"])

        assert result.exit_code != 0
        assert "assets install failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=True, output="install complete")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsInstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "install", "--operator", "claude"])

        assert result.exit_code == 0


class TestAssetsStatusExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=False, error="assets status failed")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "status"])

        assert result.exit_code != 0
        assert "assets status failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=True, output="nothing installed")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "status"])

        assert result.exit_code == 0


class TestAssetsRefreshExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=False, error="assets refresh failed")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsRefresh",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "refresh"])

        assert result.exit_code != 0
        assert "assets refresh failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=True, output="refreshed")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsRefresh",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "refresh"])

        assert result.exit_code == 0


class TestAssetsUninstallExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=False, error="assets uninstall failed")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsUninstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "uninstall", "--operator", "claude"])

        assert result.exit_code != 0
        assert "assets uninstall failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, runner: CliRunner) -> None:
        fake_result = CommandResult(success=True, output="uninstalled")
        mocker.patch(
            "klyreon.commands.assets.CommandAssetsUninstall",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["assets", "uninstall", "--operator", "claude"])

        assert result.exit_code == 0
