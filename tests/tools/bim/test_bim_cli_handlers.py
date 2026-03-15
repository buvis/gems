from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import cli
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


class TestFormatHandlerOutputBranches:
    """Cover format_note CLI handler output branches (written_to, diff, highlight, raw, formatted_count)."""

    def test_format_written_to(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={"written_to": "/tmp/out.md"},
            )

            result = runner.invoke(cli, ["format", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.success.assert_called_once_with("Formatted note written to /tmp/out.md")

    def test_format_diff_output(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                output="formatted text",
                metadata={"original": "original text"},
            )

            result = runner.invoke(cli, ["format", str(note), "--diff"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.print_side_by_side.assert_called_once_with(
                "Original",
                "original text",
                "Formatted",
                "formatted text",
                mode_left="raw",
                mode_right="markdown_with_frontmatter",
            )

    def test_format_highlight_output(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                output="formatted text",
                metadata={},
            )

            result = runner.invoke(cli, ["format", str(note), "--highlight"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.print.assert_called_once_with("formatted text", mode="markdown_with_frontmatter")

    def test_format_raw_output(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                output="formatted text",
                metadata={},
            )

            result = runner.invoke(cli, ["format", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.print.assert_called_once_with("formatted text", mode="raw")

    def test_format_formatted_count(self, runner: CliRunner, tmp_path: Path) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={"formatted_count": 2},
            )

            result = runner.invoke(cli, ["format", str(a), str(b)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.success.assert_called_once_with("Formatted 2 files")

    def test_format_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=False,
                error="Parse error",
                warnings=["warn1"],
            )

            result = runner.invoke(cli, ["format", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Parse error")
            mock_console.warning.assert_called_once_with("warn1")

    def test_format_no_paths_no_query(self, runner: CliRunner) -> None:
        with patch("bim.shared.query_paths.console") as mock_console:
            result = runner.invoke(cli, ["format"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Provide paths or -Q/-q")


class TestSyncHandlerBranches:
    def test_sync_success_with_output(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(adapters={"jira": {}})
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Synced 1", warnings=["w1"])

            result = runner.invoke(cli, ["sync", str(note), "-t", "jira"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.success.assert_called_once_with("Synced 1")
            mock_console.warning.assert_called_once_with("w1")

    def test_sync_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(adapters={"jira": {}})
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=False, error="Sync error")

            result = runner.invoke(cli, ["sync", str(note), "-t", "jira"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Sync error")

    def test_sync_not_supported(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(adapters={})
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            mock_cmd.side_effect = NotImplementedError()

            result = runner.invoke(cli, ["sync", str(note), "-t", "github"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("Sync target 'github' not supported")

    def test_sync_value_error(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(adapters={})
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            mock_cmd.side_effect = ValueError("bad config")

            result = runner.invoke(cli, ["sync", str(note), "-t", "jira"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("bad config")

    def test_sync_batch_confirm_denied(self, runner: CliRunner, tmp_path: Path) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.cli.console") as mock_console,
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(adapters={})
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            mock_console.confirm.return_value = False

            result = runner.invoke(cli, ["sync", str(a), str(b), "-t", "jira"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_cmd.assert_not_called()


class TestImportHandlerBranches:
    def test_import_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.import_note.import_note.CommandImportNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=False, error="Import failed", warnings=["w1"])

            result = runner.invoke(
                cli,
                ["import", str(note), "--tags", "a"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Import failed")
            mock_console.warning.assert_called_once_with("w1")


class TestArchiveHandlerBranches:
    def test_archive_success(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.archive_note.archive_note.CommandArchiveNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_archive=str(tmp_path / "archive"),
            )
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Archived 1", warnings=[])

            result = runner.invoke(cli, ["archive", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.success.assert_called_once_with("Archived 1")

    def test_archive_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.archive_note.archive_note.CommandArchiveNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_archive=str(tmp_path / "archive"),
            )
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=False, error="Archive error")

            result = runner.invoke(cli, ["archive", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Archive error")


class TestQueryHandlerBranches:
    def test_query_no_results(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.dependencies.parse_query_string") as mock_parse,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_evaluator") as mock_get_evaluator,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk", path_archive="/tmp/archive")
            spec = MagicMock()
            spec.source.extensions = [".md"]
            mock_parse.return_value = spec
            mock_get_repo.return_value = MagicMock()
            mock_get_evaluator.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={"rows": [], "columns": [], "directory": "/tmp", "spec": spec},
            )

            result = runner.invoke(cli, ["query", "-q", "sort: title"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.warning.assert_called_once_with("No results")


class TestCreateHandlerBranches:
    def test_create_list_templates(self, runner: CliRunner) -> None:
        with (
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_templates.return_value = {"note": MagicMock(), "project": MagicMock()}

            result = runner.invoke(cli, ["create", "--list"], catch_exceptions=False)

            assert result.exit_code == 0
            assert mock_console.print.call_count == 2

    def test_create_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=False, error="Template error", warnings=["w1"])

            result = runner.invoke(
                cli,
                ["create", "--type", "note", "--title", "X"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Template error")

    def test_create_file_not_found(self, runner: CliRunner, tmp_path: Path) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            mock_cmd.side_effect = FileNotFoundError("template not found")

            result = runner.invoke(
                cli,
                ["create", "--type", "note", "--title", "X"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("template not found")


class TestDeleteHandlerBranches:
    def test_delete_success_with_count(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, metadata={"deleted_count": 3}, warnings=["w1"])

            result = runner.invoke(cli, ["delete", str(note), "--force"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.success.assert_called_once_with("Deleted 3 zettel(s)")
            mock_console.warning.assert_called_once_with("w1")

    def test_delete_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=False, error="Delete error")

            result = runner.invoke(cli, ["delete", str(note), "--force"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Delete error")

    def test_delete_batch_confirm_denied(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.cli.console") as mock_console,
            patch("bim.shared.query_paths.resolve_query_paths") as mock_resolve,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_resolve.return_value = [Path("/a.md"), Path("/b.md")]
            mock_console.confirm.return_value = False

            result = runner.invoke(cli, ["delete", "-q", "sort: title"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_cmd.assert_not_called()


class TestShowHandlerBranches:
    def test_show_with_output(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="rendered content")

            result = runner.invoke(cli, ["show", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.print.assert_called_once_with("rendered content", mode="raw")

    def test_show_failure(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
            patch("bim.cli.console") as mock_console,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=False, error="Show error")

            result = runner.invoke(cli, ["show", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Show error")


class TestResolvePathsBranches:
    def test_paths_and_query_conflict(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with patch("bim.shared.query_paths.console") as mock_console:
            result = runner.invoke(cli, ["format", str(note), "-q", "sort: title"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.failure.assert_called_once_with("Provide paths or -Q/-q, not both")
