from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from bim.cli import create_note
from bim.params.create_note import CreateNoteParams
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


class TestCreateNoteCli:
    def test_list_templates(self, runner: CliRunner) -> None:
        with (
            patch("bim.dependencies.get_templates") as mock_templates,
            patch("bim.cli.console") as mock_console,
        ):
            mock_templates.return_value = ["beta", "alpha"]
            result = runner.invoke(create_note, ["--list"], catch_exceptions=False)

        assert result.exit_code == 0
        mock_templates.assert_called_once_with()
        mock_console.print.assert_any_call("alpha", mode="raw")
        mock_console.print.assert_any_call("beta", mode="raw")

    def test_create_note_with_type_and_title(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Created note.md")

            result = runner.invoke(
                create_note,
                ["-t", "note", "--title", "Test"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=CreateNoteParams(
                    zettel_type="note",
                    title="Test",
                    tags=None,
                    extra_answers={},
                ),
                path_zettelkasten=Path("/tmp/zk").expanduser().resolve(),
                repo=ANY,
                templates=ANY,
                hook_runner=ANY,
            )
            instance.execute.assert_called_once_with()

    def test_create_note_tags_and_answers(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Created note.md")

            result = runner.invoke(
                create_note,
                [
                    "-t",
                    "note",
                    "--title",
                    "Test",
                    "--tags",
                    "a,b",
                    "-a",
                    "first=1",
                    "-a",
                    "second=two",
                ],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=CreateNoteParams(
                    zettel_type="note",
                    title="Test",
                    tags="a,b",
                    extra_answers={"first": "1", "second": "two"},
                ),
                path_zettelkasten=Path("/tmp/zk").expanduser().resolve(),
                repo=ANY,
                templates=ANY,
                hook_runner=ANY,
            )
            instance.execute.assert_called_once_with()

    def test_create_note_without_type_or_title_launches_tui(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.tui.CreateNoteApp") as mock_app,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")

            result = runner.invoke(
                create_note,
                ["--tags", "a,b"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_app.assert_called_once_with(
                path_zettelkasten=Path("/tmp/zk").expanduser().resolve(),
                preselected_type=None,
                preselected_title=None,
                preselected_tags="a,b",
                extra_answers={},
            )
            mock_app.return_value.run.assert_called_once_with()

    def test_execute_file_not_found_calls_panic(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.cli.console") as mock_console,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            mock_cmd.side_effect = FileNotFoundError("missing template")

            result = runner.invoke(
                create_note, ["-t", "note", "--title", "X"], catch_exceptions=False
            )

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("missing template")
