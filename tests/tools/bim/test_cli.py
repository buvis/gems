from __future__ import annotations

from unittest.mock import MagicMock, patch

from bim.cli import cli


class TestShowCommand:
    def test_show_existing_file(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd:
            instance = mock_cmd.return_value

            result = runner.invoke(cli, ["show", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(paths=[note])
            instance.execute.assert_called_once_with()

    def test_show_missing_file(self, runner):
        result = runner.invoke(cli, ["show", "/nonexistent.md"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "doesn't exist" in result.output


class TestDeleteCommand:
    def test_delete_with_force(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd:
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["delete", str(note), "--force"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(paths=[note], force=True, batch=False)
            instance.execute.assert_called_once_with()

    def test_delete_multiple(self, runner, tmp_path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("# A")
        b.write_text("# B")

        with patch("bim.commands.delete_note.delete_note.CommandDeleteNote") as mock_cmd:
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["delete", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(paths=[a, b], force=False, batch=False)
            instance.execute.assert_called_once_with()


class TestImportCommand:
    def test_import_existing_file(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.import_note.import_note.CommandImportNote") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

            result = runner.invoke(cli, ["import", str(note)], catch_exceptions=False)

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[note],
                path_zettelkasten=tmp_path.resolve(),
                tags=None,
                force=False,
                remove_original=False,
                scripted=False,
            )
            instance.execute.assert_called_once_with()

    def test_import_with_flags(self, runner, tmp_path):
        note = tmp_path / "note.md"
        note.write_text("# Test")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.import_note.import_note.CommandImportNote") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["import", str(note), "--tags", "a,b", "--force", "--remove-original"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[note],
                path_zettelkasten=tmp_path.resolve(),
                tags=["a", "b"],
                force=True,
                remove_original=True,
                scripted=True,
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
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["import", str(a), str(b), "--force"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[a, b],
                path_zettelkasten=tmp_path.resolve(),
                tags=None,
                force=True,
                remove_original=False,
                scripted=True,
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
                is_highlighting_requested=True,
                is_diff_requested=True,
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

            result = runner.invoke(
                cli,
                ["format", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                paths=[a, b],
                is_highlighting_requested=False,
                is_diff_requested=False,
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
        ):
            mock_settings.return_value = MagicMock(model_extra={"jira_adapter": {"host": "jira.example"}})
            instance = mock_cmd.return_value

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
                force=False,
            )
            instance.execute.assert_called_once_with()


class TestParseTagsCommand:
    def test_parse_tags_existing_file(self, runner, tmp_path):
        tags_file = tmp_path / "tags.json"
        tags_file.write_text('{"tags": []}')
        output_path = tmp_path / "parsed.json"

        with patch("bim.commands.parse_tags.parse_tags.CommandParseTags") as mock_cmd:
            instance = mock_cmd.return_value

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
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

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
                zettel_type="note",
                title="My Title",
                tags="one,two",
                extra_answers={"q1": "a1"},
                batch_file=None,
            )
            instance.execute.assert_called_once_with()


    def test_create_batch_yaml(self, runner, tmp_path):
        spec = tmp_path / "batch.yaml"
        spec.write_text("type: note\nitems:\n  - title: A\n  - title: B\n")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["create", "--batch", str(spec)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path_zettelkasten=tmp_path.resolve(),
                zettel_type=None,
                title=None,
                tags=None,
                extra_answers={},
                batch_file=spec,
            )
            instance.execute.assert_called_once_with()

    def test_create_batch_csv(self, runner, tmp_path):
        spec = tmp_path / "batch.csv"
        spec.write_text("title,type\nAlice,contact\n")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["create", "--batch", str(spec), "--type", "note"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path_zettelkasten=tmp_path.resolve(),
                zettel_type="note",
                title=None,
                tags=None,
                extra_answers={},
                batch_file=spec,
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
