from __future__ import annotations

from types import SimpleNamespace

from buvis.pybase.result import CommandResult
from click.testing import CliRunner
from postup.adapters.cli import cli


class TestCollectExitCode:
    def test_exits_nonzero_on_failure(self, mocker, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=False, error="collect failed")
        mocker.patch(
            "postup.commands.collect.collect.CommandCollect",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["collect"])

        assert result.exit_code != 0

    def test_exits_zero_on_success(self, mocker, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=True)
        mocker.patch(
            "postup.commands.collect.collect.CommandCollect",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["collect"])

        assert result.exit_code == 0


class TestEnrichExitCode:
    def test_exits_nonzero_on_failure(self, mocker, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=False, error="enrich failed")
        mocker.patch(
            "postup.commands.enrich.enrich.CommandEnrich",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["enrich"])

        assert result.exit_code != 0

    def test_exits_zero_on_success(self, mocker, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=True)
        mocker.patch(
            "postup.commands.enrich.enrich.CommandEnrich",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["enrich"])

        assert result.exit_code == 0


class TestTuiExitCode:
    def test_exits_nonzero_on_failure(self, mocker, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=False, error="tui failed")
        mocker.patch(
            "postup.commands.tui.tui.CommandTui",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["tui"])

        assert result.exit_code != 0


class TestServeExitCode:
    def test_exits_nonzero_on_failure(self, mocker, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        fake_result = CommandResult(success=False, error="serve failed")
        mocker.patch(
            "postup.commands.serve.serve.CommandServe",
            return_value=SimpleNamespace(execute=lambda: fake_result),
        )

        result = CliRunner().invoke(cli, ["serve", "--no-browser"])

        assert result.exit_code != 0
