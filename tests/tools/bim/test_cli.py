from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from bim.cli import _resolve_output_path, cli
from bim.params.create_note import CreateNoteParams
from bim.params.delete_note import DeleteNoteParams
from bim.params.format_note import FormatNoteParams
from bim.params.import_note import ImportNoteParams
from bim.params.query import QueryParams
from bim.params.show_note import ShowNoteParams
from bim.params.sync_note import SyncNoteParams
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
            mock_cmd.assert_called_once_with(
                params=ShowNoteParams(paths=[note]),
                repo=ANY,
                formatter=ANY,
            )
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
                params=ShowNoteParams(paths=[Path("/nonexistent.md")]),
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
            mock_cmd.assert_called_once_with(params=DeleteNoteParams(paths=[a, b]), repo=ANY)
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
            settings = MagicMock(path_zettelkasten=str(tmp_path))
            mock_settings.return_value = settings

            result = runner.invoke(cli, ["import", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_interactive.assert_called_once_with(note, tmp_path.resolve(), settings)

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

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
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
                params=FormatNoteParams(paths=[note], path_output=output_path, highlight=True, diff=True),
                repo=ANY,
                formatter=ANY,
            )
            instance.execute.assert_called_once_with()

    def test_format_multiple(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with (
            patch("bim.commands.format_note.format_note.CommandFormatNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_get_repo.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True)

            result = runner.invoke(
                cli,
                ["format", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=FormatNoteParams(paths=[a, b], path_output=None),
                repo=ANY,
                formatter=ANY,
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
            mock_settings.return_value = MagicMock(adapters={"jira": {"host": "jira.example"}})
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
                params=SyncNoteParams(paths=[note], target_system="jira"),
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


class TestQueryCommand:
    def test_query_with_file(self, runner, tmp_path):
        query_file = tmp_path / "query.yml"
        query_file.write_text("sort: title\n")
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.dependencies.resolve_query_file") as mock_resolve,
            patch("bim.dependencies.parse_query_file") as mock_parse,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_evaluator") as mock_get_evaluator,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
            patch("bim.shared.query_presentation.present_query_result") as mock_present,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_archive=str(archive_dir),
            )
            spec = MagicMock()
            spec.source.extensions = [".md"]
            mock_resolve.return_value = query_file
            mock_parse.return_value = spec
            repo = MagicMock()
            evaluator = MagicMock()
            mock_get_repo.return_value = repo
            mock_get_evaluator.return_value = evaluator
            instance = mock_cmd.return_value
            rows = [{"title": "Note"}]
            columns = ["title"]
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={
                    "rows": rows,
                    "columns": columns,
                    "count": len(rows),
                    "directory": str(tmp_path),
                    "spec": spec,
                },
            )

            result = runner.invoke(
                cli,
                ["query", "--query-file", str(query_file)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_resolve.assert_called_once_with(str(query_file), bundled_dir=ANY)
            mock_parse.assert_called_once_with(str(query_file))
            mock_get_repo.assert_called_once_with(extensions=spec.source.extensions)
            mock_get_evaluator.assert_called_once_with()
            mock_cmd.assert_called_once_with(
                params=QueryParams(
                    spec=spec,
                    default_directory=str(tmp_path.resolve()),
                ),
                repo=repo,
                evaluator=evaluator,
            )
            instance.execute.assert_called_once_with()
            mock_present.assert_called_once_with(
                rows,
                columns,
                spec,
                tui=False,
                edit=False,
                archive_directory=str(archive_dir.resolve()),
                directory=str(tmp_path),
                repo=repo,
                evaluator=evaluator,
            )

    def test_query_with_inline(self, runner, tmp_path):
        archive_dir = tmp_path / "archive"

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.dependencies.parse_query_string") as mock_parse,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_evaluator") as mock_get_evaluator,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
            patch("bim.shared.query_presentation.present_query_result") as mock_present,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_archive=str(archive_dir),
            )
            spec = MagicMock()
            spec.source.extensions = [".md"]
            mock_parse.return_value = spec
            repo = MagicMock()
            evaluator = MagicMock()
            mock_get_repo.return_value = repo
            mock_get_evaluator.return_value = evaluator
            instance = mock_cmd.return_value
            rows = [{"title": "Note"}]
            columns = ["title"]
            instance.execute.return_value = CommandResult(
                success=True,
                metadata={
                    "rows": rows,
                    "columns": columns,
                    "count": len(rows),
                    "directory": str(tmp_path),
                    "spec": spec,
                },
            )

            result = runner.invoke(
                cli,
                ["query", "--query", "sort: title"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_parse.assert_called_once_with("sort: title")
            mock_get_repo.assert_called_once_with(extensions=spec.source.extensions)
            mock_get_evaluator.assert_called_once_with()
            mock_cmd.assert_called_once_with(
                params=QueryParams(
                    spec=spec,
                    default_directory=str(tmp_path.resolve()),
                ),
                repo=repo,
                evaluator=evaluator,
            )
            instance.execute.assert_called_once_with()
            mock_present.assert_called_once_with(
                rows,
                columns,
                spec,
                tui=False,
                edit=False,
                archive_directory=str(archive_dir.resolve()),
                directory=str(tmp_path),
                repo=repo,
                evaluator=evaluator,
            )
