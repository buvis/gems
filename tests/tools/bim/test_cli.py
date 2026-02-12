from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bim.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


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
                path_note=note,
                path_zettelkasten=tmp_path.resolve(),
            )
            instance.execute.assert_called_once_with()


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
                path_note=note,
                is_highlighting_requested=True,
                is_diff_requested=True,
                path_output=output_path,
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
            mock_settings.return_value = MagicMock(
                model_extra={"jira_adapter": {"host": "jira.example"}}
            )
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["sync", str(note), "jira"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path_note=note,
                target_system="jira",
                jira_adapter_config={"host": "jira.example"},
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
            )
            instance.execute.assert_called_once_with()


class TestQueryCommand:
    def test_query_with_file(self, runner, tmp_path):
        query_file = tmp_path / "query.yml"
        query_file.write_text("sort: title\n")

        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["query", "--file", str(query_file)],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                default_directory=str(tmp_path.resolve()),
                file=str(query_file),
                query=None,
                edit=False,
            )
            instance.execute.assert_called_once_with()

    def test_query_with_inline(self, runner, tmp_path):
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.query.query.CommandQuery") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten=str(tmp_path))
            instance = mock_cmd.return_value

            result = runner.invoke(
                cli,
                ["query", "--query", "sort: title"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                default_directory=str(tmp_path.resolve()),
                file=None,
                query="sort: title",
                edit=False,
            )
            instance.execute.assert_called_once_with()
