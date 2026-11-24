from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
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

    def test_missing_note_is_reported_once(self, runner: CliRunner, tmp_path: Path) -> None:
        missing = tmp_path / "missing.md"

        result = runner.invoke(cli, ["show", str(missing)])

        assert result.exit_code == 1
        # Rich wraps long tmp paths at 80 columns (PRD 00168); compare unwrapped text.
        assert " ".join(result.output.split()).count("missing.md doesn't exist") == 1
        assert "✘" in result.output
        assert "⚠" not in result.output


class TestInlineQueryErrors:
    def test_malformed_inline_query_is_a_console_error(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["query", "-q", "not: [valid"])

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "invalid query" in result.output
        assert "Traceback" not in result.output

    def test_inline_query_that_is_not_a_mapping_is_a_console_error(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["query", "-q", "just a string"])

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "invalid query: Query string must be a YAML mapping" in result.output

    @pytest.mark.parametrize("query", ["output: json", "filter: {and: 1}", 'sort: ["[/x]"]'])
    def test_inline_query_of_the_wrong_shape_is_a_console_error(self, runner: CliRunner, query: str) -> None:
        result = runner.invoke(cli, ["query", "-q", query])

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "invalid query" in result.output

    def test_malformed_inline_query_on_a_note_command_is_a_console_error(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["show", "-q", "not: [valid"])

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit)
        assert "invalid query" in result.output
