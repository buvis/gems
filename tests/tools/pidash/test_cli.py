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

    def test_help_shows_cleanup(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "cleanup" in result.output.lower()

    def test_nonexistent_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["/nonexistent/path"])
        assert result.exit_code != 0

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
