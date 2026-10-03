from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from bim.cli import cli
from bim.params.create_note import CreateNoteParams
from bim.params.delete_note import DeleteNoteParams
from bim.params.import_note import ImportNoteParams
from bim.shared.import_helpers import resolve_output_path
from buvis.pybase.result import CommandResult


class TestDeleteCommand:
    def test_delete_with_force(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={"deleted_count": 1},
            )

            result = runner.invoke(
                cli,
                ["delete", str(note), "--force"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(params=DeleteNoteParams(paths=[note], force=True), repo=ANY)
            instance.execute.assert_called_once_with()

    def test_delete_multiple(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.note_write_cli.console.confirm", return_value=True) as mock_confirm,
        ):
            mock_get_repo.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={"deleted_count": 2},
            )

            result = runner.invoke(
                cli,
                ["delete", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(params=DeleteNoteParams(paths=[a, b]), repo=ANY)
            instance.execute.assert_called_once_with()
            assert mock_confirm.call_count == 2


class TestImportCommand:
    def test_import_existing_file(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.shared.import_helpers.interactive_import") as mock_interactive,
        ):
            settings = MagicMock(path_zettelkasten=str(tmp_path))
            mock_settings.return_value = settings

            result = runner.invoke(cli, ["import", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_interactive.assert_called_once_with(note, tmp_path.resolve(), settings)

    def test_import_with_flags(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.import_note.import_note.CommandImportNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Imported note.md")

            result = runner.invoke(
                cli,
                ["import", str(note), "--tags", "a,b", "--force", "--remove-original"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=ImportNoteParams(
                    paths=[note],
                    tags=["a", "b"],
                    force=True,
                    remove_original=True,
                ),
                path_zettelkasten=tmp_path.resolve(),
                repo=ANY,
                formatter=ANY,
            )
            instance.execute.assert_called_once_with()

    def test_import_multiple_scripted(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.import_note.import_note.CommandImportNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Imported note.md")

            result = runner.invoke(
                cli,
                ["import", str(a), str(b), "--force"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=ImportNoteParams(
                    paths=[a, b],
                    tags=None,
                    force=True,
                    remove_original=False,
                ),
                path_zettelkasten=tmp_path.resolve(),
                repo=ANY,
                formatter=ANY,
            )
            instance.execute.assert_called_once_with()

    def test_import_multiple_interactive_errors(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with patch("bim.note_write_cli.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))

            result = runner.invoke(
                cli,
                ["import", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            assert "interactive import requires a single path" in result.output


class TestImportInteractiveHelpers:
    def test_resolves_next_available_id_and_updates_metadata(
        self,
        tmp_path: Path,
    ) -> None:
        path_note = tmp_path / "note.md"
        path_note.write_text("# Test", encoding="utf-8")
        note = MagicMock()
        note.id = 1
        note.data = MagicMock()
        note.data.metadata = {"id": 1}
        zettelkasten_dir = tmp_path / "zettelkasten"
        zettelkasten_dir.mkdir()

        for note_id in (1, 2, 3):
            (zettelkasten_dir / f"{note_id}.md").write_text("existing", encoding="utf-8")

        path_output = zettelkasten_dir / "1.md"

        with patch("bim.shared.import_helpers.console") as mock_console:
            mock_console.confirm.side_effect = [False, True]

            resolved_path = resolve_output_path(note, path_output, path_note, zettelkasten_dir)

        assert resolved_path == zettelkasten_dir / "4.md"
        assert note.data.metadata["id"] == 4


class TestCreateCommand:
    def test_create_scripted(self, runner, tmp_path):
        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Created note.md")

            result = runner.invoke(
                cli,
                [
                    "create",
                    "--type",
                    "note",
                    "--title",
                    "My Title",
                    "--tags",
                    "one,two",
                    "--answer",
                    "q1=a1",
                ],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=CreateNoteParams(
                    zettel_type="note",
                    title="My Title",
                    tags="one,two",
                    extra_answers={"q1": "a1"},
                ),
                path_zettelkasten=tmp_path.resolve(),
                repo=ANY,
                templates=ANY,
                hook_runner=ANY,
            )
            instance.execute.assert_called_once_with()
