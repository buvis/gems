from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import cli
from buvis.pybase.result import CommandResult
from click.testing import CliRunner

# ``query`` is not covered here: its failure path calls ``console.panic``
# directly, never ``console.report_result``, so it is out of this task's scope.


class TestFormatExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="format failed")
            result = runner.invoke(cli, ["format", str(note)], catch_exceptions=False)

        assert result.exit_code != 0
        assert "format failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, output="# Formatted")
            result = runner.invoke(cli, ["format", str(note)], catch_exceptions=False)

        assert result.exit_code == 0


class TestSyncExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.note_read_cli.get_settings", return_value=MagicMock(adapters={"jira": {}})),
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="sync failed")
            result = runner.invoke(cli, ["sync", str(note), "-t", "jira"], catch_exceptions=False)

        assert result.exit_code != 0
        assert "sync failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.note_read_cli.get_settings", return_value=MagicMock(adapters={"jira": {}})),
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, output="Synced")
            result = runner.invoke(cli, ["sync", str(note), "-t", "jira"], catch_exceptions=False)

        assert result.exit_code == 0


class TestShowExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="show failed")
            result = runner.invoke(cli, ["show", str(note)], catch_exceptions=False)

        assert result.exit_code != 0
        assert "show failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, output="# Note body")
            result = runner.invoke(cli, ["show", str(note)], catch_exceptions=False)

        assert result.exit_code == 0
