from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest
from bim.note_write_cli import create_note
from bim.params.create_note import CreateNoteParams
from buvis.pybase.result import CommandResult
from click.testing import CliRunner


class TestCreateNoteCli:
    @pytest.mark.parametrize("option", ["--source", "--body-file", "--summary-file", "settings"])
    @pytest.mark.parametrize("as_json", [True, False])
    def test_home_expansion_failure_is_reported(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, option: str, as_json: bool
    ) -> None:
        original_expanduser = Path.expanduser

        def expanduser(path: Path) -> Path:
            if str(path).startswith("~missing/"):
                raise RuntimeError("Could not determine home directory.")
            return original_expanduser(path)

        monkeypatch.setattr(Path, "expanduser", expanduser)
        args = ["-t", "article", "--title", "Test"]
        if option != "settings":
            args.extend([option, "~missing/input.md"])
        if as_json:
            args.append("--json")
        with patch("bim.note_write_cli.get_settings", autospec=True) as settings:
            settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects="~missing/projects" if option == "settings" else str(tmp_path),
                path_daily=str(tmp_path),
                path_articles=str(tmp_path),
            )
            result = runner.invoke(create_note, args, catch_exceptions=False)

        assert result.exit_code == 1
        if as_json:
            assert json.loads(result.output) == {"error": "Could not determine home directory."}
        else:
            assert "Could not determine home directory." in result.output
            assert "Traceback" not in result.output
        assert list(tmp_path.iterdir()) == []

    def test_list_templates(self, runner: CliRunner) -> None:
        with (
            patch("bim.dependencies.get_templates") as mock_templates,
            patch("bim.note_write_cli.console") as mock_console,
        ):
            mock_templates.return_value = ["beta", "alpha"]
            result = runner.invoke(create_note, ["--list"], catch_exceptions=False)

        assert result.exit_code == 0
        mock_templates.assert_called_once_with()
        mock_console.print.assert_any_call("alpha", mode="raw")
        mock_console.print.assert_any_call("beta", mode="raw")

    def test_create_note_with_type_and_title(self, runner: CliRunner) -> None:
        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo"),
            patch("bim.dependencies.get_templates"),
            patch("bim.dependencies.get_hook_runner"),
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_projects="/tmp/projects",
                path_daily="/tmp/daily",
                path_articles="/tmp/articles",
            )
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Created note.md")

            result = runner.invoke(create_note, ["-t", "note", "--title", "Test"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_cmd.assert_called_once_with(
                params=CreateNoteParams(zettel_type="note", title="Test", tags=None, extra_answers={}),
                path_zettelkasten=Path("/tmp/zk").expanduser().resolve(),
                repo=ANY,
                templates=ANY,
                hook_runner=ANY,
                formatter=mock_get_formatter.return_value,
                path_daily=Path("/tmp/daily"),
                path_articles=Path("/tmp/articles"),
            )
            instance.execute.assert_called_once_with()

    def test_create_note_tags_and_answers(self, runner: CliRunner) -> None:
        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo"),
            patch("bim.dependencies.get_templates"),
            patch("bim.dependencies.get_hook_runner"),
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_projects="/tmp/projects",
                path_daily="/tmp/daily",
                path_articles="/tmp/articles",
            )
            instance = mock_cmd.return_value
            instance.execute.return_value = CommandResult(success=True, output="Created note.md")

            result = runner.invoke(
                create_note,
                ["-t", "note", "--title", "Test", "--tags", "a,b", "-a", "first=1", "-a", "second=two"],
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
                formatter=mock_get_formatter.return_value,
                path_daily=Path("/tmp/daily"),
                path_articles=Path("/tmp/articles"),
            )
            instance.execute.assert_called_once_with()

    def test_create_note_without_type_or_title_launches_tui(self, runner: CliRunner) -> None:
        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.tui.create_note.CreateNoteApp") as mock_app,
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_projects="/tmp/projects",
                path_daily="/tmp/daily",
                path_articles="/tmp/articles",
            )

            result = runner.invoke(create_note, ["--tags", "a,b"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_app.assert_called_once_with(
                path_zettelkasten=Path("/tmp/zk").expanduser().resolve(),
                preselected_type=None,
                preselected_title=None,
                preselected_tags="a,b",
                extra_answers={},
                path_projects=Path("/tmp/projects"),
                path_daily=Path("/tmp/daily"),
                path_articles=Path("/tmp/articles"),
            )
            mock_app.return_value.run.assert_called_once_with()

    def test_execute_file_not_found_calls_panic(self, runner: CliRunner) -> None:
        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.note_write_cli.console") as mock_console,
            patch("bim.dependencies.get_repo"),
            patch("bim.dependencies.get_templates"),
            patch("bim.dependencies.get_hook_runner"),
            patch("bim.dependencies.get_formatter"),
        ):
            mock_settings.return_value = MagicMock(
                path_zettelkasten="/tmp/zk",
                path_projects="/tmp/projects",
                path_daily="/tmp/daily",
                path_articles="/tmp/articles",
            )
            mock_cmd.side_effect = FileNotFoundError("missing template")

            result = runner.invoke(create_note, ["-t", "note", "--title", "X"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("missing template")

    def test_body_source_conflict_precedes_source_expansion(self, runner: CliRunner, tmp_path: Path) -> None:
        with patch("bim.note_write_cli.get_settings") as settings:
            settings.return_value = MagicMock(
                path_zettelkasten=str(tmp_path),
                path_projects=str(tmp_path),
                path_daily=str(tmp_path),
                path_articles=str(tmp_path),
            )
            result = runner.invoke(
                create_note, ["--body-file", "missing.md", "--source", "~bim_nonexistent_user/inbox.md", "--json"]
            )
        assert result.exit_code == 1
        assert result.output.strip() == '{"error": "--body-file and --source are mutually exclusive"}'
