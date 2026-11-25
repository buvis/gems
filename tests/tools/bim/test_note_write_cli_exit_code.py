from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import cli
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


def _settings(tmp_path: Path) -> MagicMock:
    return MagicMock(
        path_zettelkasten=str(tmp_path),
        path_projects=str(tmp_path / "projects"),
        path_daily=str(tmp_path / "daily"),
        path_articles=str(tmp_path / "articles"),
        path_archive=str(tmp_path / "archive"),
    )


class TestImportExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.note_write_cli.get_settings", return_value=_settings(tmp_path)),
            patch("bim.commands.import_note.import_note.CommandImportNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="import failed")
            result = runner.invoke(cli, ["import", str(note), "--force"], catch_exceptions=False)

        assert result.exit_code != 0
        assert "import failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.note_write_cli.get_settings", return_value=_settings(tmp_path)),
            patch("bim.commands.import_note.import_note.CommandImportNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_formatter", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, output="imported note.md")
            result = runner.invoke(cli, ["import", str(note), "--force"], catch_exceptions=False)

        assert result.exit_code == 0


class TestCreateExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        with (
            patch("bim.note_write_cli.get_settings", return_value=_settings(tmp_path)),
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_templates", return_value=MagicMock()),
            patch("bim.dependencies.get_hook_runner", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="create failed")
            result = runner.invoke(
                cli,
                ["create", "--type", "note", "--title", "My Title"],
                catch_exceptions=False,
            )

        assert result.exit_code != 0
        assert "create failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        with (
            patch("bim.note_write_cli.get_settings", return_value=_settings(tmp_path)),
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
            patch("bim.dependencies.get_templates", return_value=MagicMock()),
            patch("bim.dependencies.get_hook_runner", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, output="Created note.md")
            result = runner.invoke(
                cli,
                ["create", "--type", "note", "--title", "My Title"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0


class TestEditExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with (
            patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="edit failed")
            result = runner.invoke(cli, ["edit", str(note), "--title", "New"], catch_exceptions=False)

        assert result.exit_code != 0
        assert "edit failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with (
            patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, output="Updated note.md")
            result = runner.invoke(cli, ["edit", str(note), "--title", "New"], catch_exceptions=False)

        assert result.exit_code == 0


class TestArchiveExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with (
            patch("bim.note_write_cli.get_settings", return_value=_settings(tmp_path)),
            patch("bim.commands.archive_note.archive_note.CommandArchiveNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="archive failed")
            result = runner.invoke(cli, ["archive", str(note)], catch_exceptions=False)

        assert result.exit_code != 0
        assert "archive failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with (
            patch("bim.note_write_cli.get_settings", return_value=_settings(tmp_path)),
            patch("bim.commands.archive_note.archive_note.CommandArchiveNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, output="archived note.md")
            result = runner.invoke(cli, ["archive", str(note)], catch_exceptions=False)

        assert result.exit_code == 0


class TestDeleteExitCode:
    def test_exits_nonzero_when_result_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=False, error="delete failed")
            result = runner.invoke(cli, ["delete", str(note), "--force"], catch_exceptions=False)

        assert result.exit_code != 0
        assert "delete failed" in result.output

    def test_exits_zero_when_result_succeeds(self, runner: CliRunner, tmp_path: Path) -> None:
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo", return_value=MagicMock()),
        ):
            mock_cmd.return_value.execute.return_value = CommandResult(success=True, metadata={"deleted_count": 1})
            result = runner.invoke(cli, ["delete", str(note), "--force"], catch_exceptions=False)

        assert result.exit_code == 0
