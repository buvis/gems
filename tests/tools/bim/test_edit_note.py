from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from bim.cli import cli
from bim.commands.edit_note.edit_note import CommandEditNote
from bim.params.edit_note import EditNoteParams
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


@pytest.fixture
def zettel_file(tmp_path: Path, minimal_zettel: str) -> Path:
    p = tmp_path / "202401151030 Test note.md"
    p.write_text(minimal_zettel, encoding="utf-8")
    return p


class TestCommandEditNote:
    def test_scripted_updates_note(self, zettel_file: Path) -> None:
        mock_repo = MagicMock()
        mock_zettel = MagicMock()
        mock_repo.find_by_location.return_value = mock_zettel
        with patch("bim.commands.edit_note.edit_note.UpdateZettelUseCase") as mock_use_case:
            instance = mock_use_case.return_value
            params = EditNoteParams(paths=[zettel_file], changes={"title": "X"})
            cmd = CommandEditNote(params=params, repo=mock_repo)
            result = cmd.execute()

            assert result.success is True
            instance.execute.assert_called_once_with(mock_zettel, {"title": "X"}, "metadata")

    def test_batch_edits_all(self, tmp_path: Path, minimal_zettel: str) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(minimal_zettel, encoding="utf-8")
        b.write_text(minimal_zettel, encoding="utf-8")

        mock_repo = MagicMock()
        mock_zettel = MagicMock()
        mock_repo.find_by_location.return_value = mock_zettel
        with patch("bim.commands.edit_note.edit_note.UpdateZettelUseCase") as mock_use_case:
            params = EditNoteParams(paths=[a, b], changes={"title": "X"})
            cmd = CommandEditNote(params=params, repo=mock_repo)
            result = cmd.execute()

            assert result.metadata["updated_count"] == 2
            assert mock_use_case.return_value.execute.call_count == 2

    def test_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.md"
        mock_repo = MagicMock()

        params = EditNoteParams(paths=[missing], changes={"title": "X"})
        cmd = CommandEditNote(params=params, repo=mock_repo)
        result = cmd.execute()

        assert result.success is False
        assert f"{missing} doesn't exist" in result.warnings


class TestEditCliCommand:
    def test_edit_scripted(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with (
            patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Updated note.md")
            result = runner.invoke(
                cli,
                ["edit", str(note), "--title", "New", "--tags", "a,b", "--type", "project"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=EditNoteParams(
                    paths=[note],
                    changes={"title": "New", "tags": ["a", "b"], "type": "project"},
                ),
                repo=ANY,
            )
            instance.execute.assert_called_once()

    def test_edit_boolean_flags(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with (
            patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Updated note.md")
            result = runner.invoke(
                cli,
                ["edit", str(note), "--processed", "--publish"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=EditNoteParams(
                    paths=[note],
                    changes={"processed": True, "publish": True},
                ),
                repo=ANY,
            )
            instance.execute.assert_called_once()

    def test_edit_no_flags_launches_tui(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with patch("bim.commands.edit_note.tui.EditNoteApp") as mock_app:
            result = runner.invoke(
                cli,
                ["edit", str(note)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_app.assert_called_once_with(path=note)
            mock_app.return_value.run.assert_called_once()

    def test_edit_extra_set(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        note = tmp_path / "note.md"
        note.write_text(minimal_zettel)

        with (
            patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Updated note.md")
            result = runner.invoke(
                cli,
                ["edit", str(note), "-s", "custom=val"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=EditNoteParams(
                    paths=[note],
                    changes={"custom": "val"},
                ),
                repo=ANY,
            )
            instance.execute.assert_called_once()

    def test_edit_multiple_scripted(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(minimal_zettel)
        b.write_text(minimal_zettel)

        with (
            patch("bim.commands.edit_note.edit_note.CommandEditNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Updated note.md")
            result = runner.invoke(
                cli,
                ["edit", str(a), str(b), "--title", "X"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=EditNoteParams(
                    paths=[a, b],
                    changes={"title": "X"},
                ),
                repo=ANY,
            )
            instance.execute.assert_called_once()

    def test_edit_missing_file(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["edit", "/nonexistent.md"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "doesn't exist" in result.output

    def test_edit_multiple_no_changes_errors(self, runner: CliRunner, tmp_path: Path, minimal_zettel: str) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(minimal_zettel)
        b.write_text(minimal_zettel)

        result = runner.invoke(
            cli,
            ["edit", str(a), str(b)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert "TUI edit requires a single path" in result.output
