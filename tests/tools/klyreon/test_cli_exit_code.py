"""Exit-code contract for the vault-rooted klyreon commands' terminal
``console.report_result`` call: init, new, validate, export-claims,
ingest, status, maintain.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from klyreon.cli import cli

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _vault(tmp_path: Path, klyreon_env: Callable[[Path], None]) -> Path:
    root = tmp_path / "vault"
    root.mkdir()
    klyreon_env(root)
    return root


class TestInitExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        root = _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=False, error="init failed")
        mocker.patch(
            "klyreon.commands.init.CommandInit",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["init", str(root), "--no-input"])

        assert result.exit_code != 0
        assert "init failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        root = _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=True, output="vault created")
        mocker.patch(
            "klyreon.commands.init.CommandInit",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["init", str(root), "--no-input"])

        assert result.exit_code == 0


class TestNewExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=False, error="new failed")
        mocker.patch(
            "klyreon.commands.new.CommandNew",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["new", "--title", "Some Title"])

        assert result.exit_code != 0
        assert "new failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=True, output="created note")
        mocker.patch(
            "klyreon.commands.new.CommandNew",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["new", "--title", "Some Title"])

        assert result.exit_code == 0


class TestValidateExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=False, error="validation failed")
        mocker.patch(
            "klyreon.commands.validate.CommandValidate",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["validate"])

        assert result.exit_code != 0
        assert "validation failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=True, output="vault clean")
        mocker.patch(
            "klyreon.commands.validate.CommandValidate",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["validate"])

        assert result.exit_code == 0


class TestExportClaimsExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=False, error="export failed")
        mocker.patch(
            "klyreon.commands.export_claims.CommandExportClaims",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        # --out routes through console.report_result in both outcomes (the
        # print-to-stdout shortcut only applies when --out is absent AND the
        # result succeeds).
        result = runner.invoke(cli, ["export-claims", "--out", str(tmp_path / "claims.json")])

        assert result.exit_code != 0
        assert "export failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=True, output="wrote claims")
        mocker.patch(
            "klyreon.commands.export_claims.CommandExportClaims",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["export-claims", "--out", str(tmp_path / "claims.json")])

        assert result.exit_code == 0


class TestIngestExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=False, error="ingest failed")
        mocker.patch(
            "klyreon.commands.ingest.CommandIngest",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["ingest"])

        assert result.exit_code != 0
        assert "ingest failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=True, output="ingested 1 source")
        mocker.patch(
            "klyreon.commands.ingest.CommandIngest",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["ingest"])

        assert result.exit_code == 0


class TestStatusExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=False, error="status failed")
        mocker.patch(
            "klyreon.commands.status.CommandStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["status"])

        assert result.exit_code != 0
        assert "status failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=True, output="dashboard")
        mocker.patch(
            "klyreon.commands.status.CommandStatus",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0


class TestMaintainExitCode:
    def test_exits_nonzero_when_result_fails(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=False, error="maintain failed")
        mocker.patch(
            "klyreon.commands.maintain.CommandMaintain",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["maintain"])

        assert result.exit_code != 0
        assert "maintain failed" in result.output

    def test_exits_zero_when_result_succeeds(self, mocker, tmp_path, klyreon_env, runner: CliRunner) -> None:
        _vault(tmp_path, klyreon_env)
        fake_result = CommandResult(success=True, output="maintenance swept")
        mocker.patch(
            "klyreon.commands.maintain.CommandMaintain",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = runner.invoke(cli, ["maintain"])

        assert result.exit_code == 0
