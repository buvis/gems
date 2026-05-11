from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from pidash.cli import cli


class TestPidashCli:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "dashboard" in result.output.lower()

    def test_nonexistent_path_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--project-path", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_tui_subcommand_with_nonexistent_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["tui", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_hooks_help_lists_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["hooks", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output

    def test_hooks_run_unknown_event_fails(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["hooks", "run", "bogus-event"])
        assert result.exit_code != 0

    def test_hooks_run_set_attention_is_noop_without_state(self, tmp_path: Path) -> None:
        runner = CliRunner()
        # No state.json in CWD -> hook returns silently with exit 0
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["hooks", "run", "set-attention"])
        assert result.exit_code == 0

    def test_cleanup_empty_dir(self, tmp_path: Path) -> None:
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        runner = CliRunner()
        with patch("pidash.tui.watcher.SESSIONS_DIR", sessions_dir):
            result = runner.invoke(cli, ["--cleanup"])
        assert result.exit_code == 0
        assert "0" in result.output

    def test_cleanup_no_dir(self, tmp_path: Path) -> None:
        missing_dir = tmp_path / "nonexistent"
        runner = CliRunner()
        with patch("pidash.tui.watcher.SESSIONS_DIR", missing_dir):
            result = runner.invoke(cli, ["--cleanup"])
        assert result.exit_code == 0
        assert "No sessions" in result.output
