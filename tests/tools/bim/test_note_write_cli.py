from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
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
            settings = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects=str(tmp_path / "projects"),
                path_daily=str(tmp_path / "daily"),
                path_articles=str(tmp_path / "articles"),
            )
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
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects=str(tmp_path / "projects"),
                path_daily=str(tmp_path / "daily"),
                path_articles=str(tmp_path / "articles"),
            )
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
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects=str(tmp_path / "projects"),
                path_daily=str(tmp_path / "daily"),
                path_articles=str(tmp_path / "articles"),
            )
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
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects=str(tmp_path / "projects"),
                path_daily=str(tmp_path / "daily"),
                path_articles=str(tmp_path / "articles"),
            )

            result = runner.invoke(
                cli,
                ["import", str(a), str(b)],
                catch_exceptions=False,
            )

            assert result.exit_code == 1
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
            mock_settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects=str(tmp_path / "projects"),
                path_daily=str(tmp_path / "daily"),
                path_articles=str(tmp_path / "articles"),
            )
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
                formatter=ANY,
                path_daily=tmp_path / "daily",
                path_articles=tmp_path / "articles",
            )
            instance.execute.assert_called_once_with()


@contextmanager
def _scripted_create(tmp_path: Path, result: CommandResult) -> Iterator[MagicMock]:
    with (
        patch(
            "bim.note_write_cli.get_settings",
            return_value=MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects=str(tmp_path / "projects"),
                path_daily=str(tmp_path / "daily"),
                path_articles=str(tmp_path / "articles"),
            ),
        ),
        patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
        patch("bim.dependencies.get_repo"),
        patch("bim.dependencies.get_templates"),
        patch("bim.dependencies.get_hook_runner"),
    ):
        mock_cmd.return_value.execute.return_value = result
        yield mock_cmd


class TestCreateScriptingContract:
    def test_json_prints_single_object_and_nothing_else(self, runner, tmp_path):
        metadata = {"id": "20261108134925", "title": "Čaj", "tags": ["a"], "wikilink": "[[notes/20261108134925|Čaj]]"}
        result = CommandResult(success=True, output="Created x", warnings=["root missing"], metadata=metadata)
        with _scripted_create(tmp_path, result):
            outcome = runner.invoke(cli, ["create", "-t", "note", "--title", "Čaj", "--json"], catch_exceptions=False)

        assert outcome.exit_code == 0
        expected = {**metadata, "warnings": ["root missing"]}
        assert outcome.output == json.dumps(expected, ensure_ascii=False) + "\n"
        assert json.loads(outcome.output) == expected

    def test_json_failure_prints_error_and_exits_1(self, runner, tmp_path):
        result = CommandResult(success=False, error="Unknown template: nonexistent", warnings=["w1"])
        with _scripted_create(tmp_path, result):
            outcome = runner.invoke(cli, ["create", "-t", "nonexistent", "--title", "X", "--json"])

        assert outcome.exit_code == 1
        assert outcome.output == '{"error": "Unknown template: nonexistent"}\n'

    def test_create_failure_exits_1(self, runner, tmp_path):
        result = CommandResult(success=False, error="Missing required answer: location")
        with (
            _scripted_create(tmp_path, result),
            patch("bim.note_write_cli.console.failure") as mock_failure,
        ):
            outcome = runner.invoke(cli, ["create", "-t", "meeting-minutes", "--title", "X"])

        assert outcome.exit_code == 1
        mock_failure.assert_called_once_with("Missing required answer: location")

    def test_body_file_and_source_fail_before_any_read(self, runner, tmp_path):
        with _scripted_create(tmp_path, CommandResult(success=True)) as mock_cmd:
            outcome = runner.invoke(
                cli,
                ["create", "-t", "note", "--body-file", str(tmp_path / "none.md"), "--source", "inbox/x.md", "--json"],
            )

        assert outcome.exit_code == 1
        assert json.loads(outcome.output) == {"error": "--body-file and --source are mutually exclusive"}
        mock_cmd.assert_not_called()

    def test_scripting_flags_skip_tui_and_read_stdin_body(self, runner, tmp_path):
        result = CommandResult(success=True, metadata={"dry_run": True, "content": "---\nid: 1\n---\n# T"})
        with (
            _scripted_create(tmp_path, result) as mock_cmd,
            patch("bim.tui.create_note.CreateNoteApp") as mock_app,
            patch("bim.note_write_cli.console.print") as mock_print,
        ):
            outcome = runner.invoke(
                cli, ["create", "-t", "note", "--body-file", "-", "--dry-run"], input="From stdin\n"
            )

        assert outcome.exit_code == 0
        mock_app.assert_not_called()
        params = mock_cmd.call_args.kwargs["params"]
        assert params == CreateNoteParams(zettel_type="note", body="From stdin\n", dry_run=True, extra_answers={})
        mock_print.assert_called_once_with("---\nid: 1\n---\n# T", mode="raw")

    def test_summary_file_rejected_for_non_article(self, runner, tmp_path):
        summary = tmp_path / "s.md"
        summary.write_text("facts")
        with (
            _scripted_create(tmp_path, CommandResult(success=True)) as mock_cmd,
            patch("bim.note_write_cli.console.panic") as mock_panic,
        ):
            runner.invoke(cli, ["create", "-t", "note", "--title", "T", "--summary-file", str(summary)])

        mock_panic.assert_called_once_with("--summary-file is only for the article template")
        mock_cmd.assert_not_called()

    def test_article_flags_and_vault_paths_reach_the_command(self, runner, tmp_path):
        body = tmp_path / "b.md"
        body.write_text("Original\n")
        summary = tmp_path / "s.md"
        summary.write_text("Facts\n")
        args = ["create", "-t", "article", "--title", "T", "--body-file", str(body), "--summary-file", str(summary)]
        with _scripted_create(tmp_path, CommandResult(success=True, metadata={})) as mock_cmd:
            outcome = runner.invoke(cli, [*args, "--no-daily-log", "--no-link-contacts", "--json"])

        assert outcome.exit_code == 0
        kwargs = mock_cmd.call_args.kwargs
        assert kwargs["params"] == CreateNoteParams(
            zettel_type="article",
            title="T",
            extra_answers={},
            body="Original\n",
            summary="Facts\n",
            daily_log=False,
            link_contacts=False,
        )
        assert kwargs["path_daily"] == tmp_path / "daily"
        assert kwargs["path_articles"] == tmp_path / "articles"

    def test_list_with_json_is_rejected_as_json(self, runner):
        with patch("bim.dependencies.get_templates") as mock_templates:
            outcome = runner.invoke(cli, ["create", "--list", "--json"])

        assert outcome.exit_code == 1
        assert json.loads(outcome.output) == {"error": "--list cannot be combined with --json"}
        mock_templates.assert_not_called()
