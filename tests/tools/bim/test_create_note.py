from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bim.cli import create_note
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
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            instance = mock_cmd.return_value

            result = runner.invoke(
                create_note,
                ["-t", "note", "--title", "Test"],
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                path_zettelkasten=Path("/tmp/zk").expanduser().resolve(),
                zettel_type="note",
                title="Test",
                tags=None,
                extra_answers={},
                batch_file=None,
            )
            instance.execute.assert_called_once_with()

    def test_create_note_tags_and_answers(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            instance = mock_cmd.return_value

            result = runner.invoke(
                create_note,
                [
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
                path_zettelkasten=Path("/tmp/zk").expanduser().resolve(),
                zettel_type=None,
                title=None,
                tags="a,b",
                extra_answers={"first": "1", "second": "two"},
                batch_file=None,
            )
            instance.execute.assert_called_once_with()

    def test_execute_file_not_found_calls_panic(self, runner: CliRunner) -> None:
        with (
            patch("bim.cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.cli.console") as mock_console,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            instance = mock_cmd.return_value
            instance.execute.side_effect = FileNotFoundError("missing template")

            result = runner.invoke(create_note, ["-t", "note"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("missing template")
