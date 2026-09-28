from __future__ import annotations

from click.testing import CliRunner
from postup.adapters.cli import cli


class TestCli:
    def test_help(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "POrtfolio STandUP" in result.output

    def test_collect_registered(self):
        result = CliRunner().invoke(cli, ["collect", "--help"])
        assert result.exit_code == 0
        assert "--no-fetch" in result.output
        assert "--days" in result.output

    def test_enrich_registered(self):
        result = CliRunner().invoke(cli, ["enrich", "--help"])
        assert result.exit_code == 0
        assert "epics.json" in result.output

    def test_collect_runs_and_reports(self, tmp_path, mocker, monkeypatch):
        # No roots configured -> command returns failure, CLI renders it without crashing.
        monkeypatch.delenv("BUVIS_POSTUP_ROOTS", raising=False)
        monkeypatch.setenv("BUVIS_POSTUP_OUT_DIR", str(tmp_path / "out"))
        result = CliRunner().invoke(cli, ["collect", "--no-fetch"])
        assert result.exit_code == 0
        assert "no repositories" in result.output
