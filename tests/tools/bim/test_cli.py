from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from bim.cli import _resolve_output_path, cli
from buvis.pybase.result import CommandResult


class TestShowCommand:
    def test_show_existing_file(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True)

            result = runner.invoke(cli, ["show", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(paths=[note], repo=ANY, formatter=ANY)
            instance.execute.assert_called_once_with()

    def test_show_missing_file(self, runner):
        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(
                success=False,
                error="Missing note",
                warnings=["Missing note"],
            )

            result = runner.invoke(cli, ["show", "/nonexistent.md"], catch_exceptions=False)
            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[Path("/nonexistent.md")],
                repo=ANY,
                formatter=ANY,
            )
            instance.execute.assert_called_once_with()
            assert "Missing note" in result.output


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
            mock_cmd.assert_called_once_with(paths=[note], repo=ANY)
            instance.execute.assert_called_once_with()

    def test_delete_multiple(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with (
            patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.cli.console.confirm", return_value=True) as mock_confirm,
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
            mock_cmd.assert_called_once_with(paths=[a, b], repo=ANY)
            instance.execute.assert_called_once_with()
            assert mock_confirm.call_count == 2


class TestImportCommand:
    def test_import_existing_file(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.cli._interactive_import") as mock_interactive,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))

            result = runner.invoke(cli, ["import", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_interactive.assert_called_once_with(note, tmp_path.resolve())

    def test_import_with_flags(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
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
                paths=[note],
                path_zettelkasten=tmp_path.resolve(),
                repo=ANY,
                formatter=ANY,
                tags=["a", "b"],
                force=True,
                remove_original=True,
            )
            instance.execute.assert_called_once_with()

    def test_import_multiple_scripted(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with (
            patch("bim.cli.get_settings") as mock_settings,
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
                paths=[a, b],
                path_zettelkasten=tmp_path.resolve(),
                repo=ANY,
                formatter=ANY,
                tags=None,
                force=True,
                remove_original=False,
            )
            instance.execute.assert_called_once_with()

    def test_import_multiple_interactive_errors(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with patch("bim.cli.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))

            result = runner.invoke(
                cli,
                ["import", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            assert "interactive import requires a single path" in result.output


class TestFormatCommand:
    def test_format_existing_file(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")
        output_path = tmp_path / "formatted.md"

        with patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd:
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True)

            result = runner.invoke(
                cli,
                [
                    "format",
                    str(note),
                    "--highlight",
                    "--diff",
                    "--output",
                    str(output_path),
                ],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[note],
                repo=ANY,
                formatter=ANY,
                path_output=output_path,
            )
            instance.execute.assert_called_once_with()

    def test_format_multiple(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd:
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True)

            result = runner.invoke(
                cli,
                ["format", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[a, b],
                repo=ANY,
                formatter=ANY,
                path_output=None,
            )
            instance.execute.assert_called_once_with()


class TestSyncCommand:
    def test_sync_existing_file(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.sync_note.sync_note.CommandSyncNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(model_extra={"jira_adapter": {"host": "jira.example"}})
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Synced")

            result = runner.invoke(
                cli,
                ["sync", str(note), "-t", "jira"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[note],
                target_system="jira",
                jira_adapter_config={"host": "jira.example"},
                repo=ANY,
                formatter=ANY,
            )
            instance.execute.assert_called_once_with()


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

        with patch("bim.cli.console") as mock_console:
            mock_console.confirm.side_effect = [False, True]

            resolved_path = _resolve_output_path(note, path_output, path_note, zettelkasten_dir)

        assert resolved_path == zettelkasten_dir / "4.md"
        assert note.data.metadata["id"] == 4


class TestParseTagsCommand:
    def test_parse_tags_existing_file(self, runner, tmp_path):
        tags_file = tmp_path / "tags.json"
        tags_file.write_text('{"tags": []}')
        output_path = tmp_path / "parsed.json"

        with patch("bim.commands.parse_tags.parse_tags.CommandParseTags") as mock_cmd:
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True)

            result = runner.invoke(
                cli,
                ["parse_tags", str(tags_file), "--output", str(output_path)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path_tags_json=tags_file,
                path_output=output_path,
            )
            instance.execute.assert_called_once_with()


class TestCreateCommand:
    def test_create_scripted(self, runner, tmp_path):
        with (
            patch("bim.cli.get_settings") as mock_settings,
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
                path_zettelkasten=tmp_path.resolve(),
                repo=ANY,
                templates=ANY,
                hook_runner=ANY,
                zettel_type="note",
                title="My Title",
                tags="one,two",
                extra_answers={"q1": "a1"},
            )
            instance.execute.assert_called_once_with()


class TestQueryCommand:
    def test_query_with_file(self, runner, tmp_path):
        query_file = tmp_path / "query.yml"
        query_file.write_text("sort: title\n")
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_archive=str(archive_dir),
            )
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["query", "--file", str(query_file)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                default_directory=str(tmp_path.resolve()),
                archive_directory=str(archive_dir.resolve()),
                file=str(query_file),
                query=None,
                edit=False,
                tui=False,
            )
            instance.execute.assert_called_once_with()

    def test_query_with_inline(self, runner, tmp_path):
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_archive=str(archive_dir),
            )
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["query", "--query", "sort: title"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                default_directory=str(tmp_path.resolve()),
                archive_directory=str(archive_dir.resolve()),
                file=None,
                query="sort: title",
                edit=False,
                tui=False,
            )
            instance.execute.assert_called_once_with()
