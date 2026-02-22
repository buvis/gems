from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from bim.cli import create_note
from bim.commands.create_note.create_note import CommandCreateNote
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
            patch("bim.tui.create_note.CreateNoteApp") as mock_app,
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

            result = runner.invoke(create_note, ["-t", "note", "--title", "X"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("missing template")


class TestCommandCreateNote:
    def test_raises_when_zettelkasten_dir_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        params = CreateNoteParams(zettel_type="note", title="Test")
        repo = MagicMock()
        templates: dict[str, MagicMock] = {}
        hook_runner = MagicMock()

        try:
            CommandCreateNote(
                params=params,
                path_zettelkasten=missing,
                repo=repo,
                templates=templates,
                hook_runner=hook_runner,
            )
            raised = False
        except FileNotFoundError:
            raised = True

        assert raised

    def test_returns_error_when_type_is_none(self, tmp_path: Path) -> None:
        params = CreateNoteParams(zettel_type=None, title="Test")
        repo = MagicMock()
        templates: dict[str, MagicMock] = {}
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates=templates,
            hook_runner=hook_runner,
        )
        result = cmd.execute()

        assert result.success is False
        assert "zettel_type and title are required" in (result.error or "")

    def test_returns_error_when_title_is_none(self, tmp_path: Path) -> None:
        params = CreateNoteParams(zettel_type="note", title=None)
        repo = MagicMock()
        templates: dict[str, MagicMock] = {}
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates=templates,
            hook_runner=hook_runner,
        )
        result = cmd.execute()

        assert result.success is False
        assert "zettel_type and title are required" in (result.error or "")

    def test_returns_error_for_unknown_template(self, tmp_path: Path) -> None:
        params = CreateNoteParams(zettel_type="bogus", title="Test")
        repo = MagicMock()
        templates = {"note": MagicMock()}
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates=templates,
            hook_runner=hook_runner,
        )
        result = cmd.execute()

        assert result.success is False
        assert "Unknown template: bogus" in (result.error or "")

    def test_execute_success(self, tmp_path: Path) -> None:
        template = MagicMock()
        template.questions.return_value = []
        params = CreateNoteParams(zettel_type="note", title="My Note", tags="a,b")
        repo = MagicMock()
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )

        created_path = tmp_path / "42.md"
        with patch("bim.commands.create_note.create_note.CreateZettelUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = created_path
            result = cmd.execute()

        assert result.success is True
        assert str(created_path) in (result.output or "")
        assert result.metadata["path"] == created_path
        mock_use_case.return_value.execute.assert_called_once_with(
            template,
            {"title": "My Note", "tags": "a,b"},
        )

    def test_execute_file_exists_error(self, tmp_path: Path) -> None:
        template = MagicMock()
        template.questions.return_value = []
        params = CreateNoteParams(zettel_type="note", title="My Note")
        repo = MagicMock()
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )

        with patch("bim.commands.create_note.create_note.CreateZettelUseCase") as mock_use_case:
            mock_use_case.return_value.execute.side_effect = FileExistsError("already exists")
            result = cmd.execute()

        assert result.success is False
        assert "already exists" in (result.error or "")

    def test_execute_uses_extra_answers(self, tmp_path: Path) -> None:
        question = MagicMock()
        question.key = "project"
        question.default = None
        question.required = False
        template = MagicMock()
        template.questions.return_value = [question]
        params = CreateNoteParams(
            zettel_type="note",
            title="My Note",
            extra_answers={"project": "alpha"},
        )
        repo = MagicMock()
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )

        with patch("bim.commands.create_note.create_note.CreateZettelUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = tmp_path / "1.md"
            result = cmd.execute()

        assert result.success is True
        call_args = mock_use_case.return_value.execute.call_args
        answers = call_args[0][1]
        assert answers["project"] == "alpha"

    def test_execute_uses_question_default(self, tmp_path: Path) -> None:
        question = MagicMock()
        question.key = "priority"
        question.default = "low"
        question.required = False
        template = MagicMock()
        template.questions.return_value = [question]
        params = CreateNoteParams(zettel_type="note", title="My Note")
        repo = MagicMock()
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )

        with patch("bim.commands.create_note.create_note.CreateZettelUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = tmp_path / "1.md"
            result = cmd.execute()

        assert result.success is True
        call_args = mock_use_case.return_value.execute.call_args
        answers = call_args[0][1]
        assert answers["priority"] == "low"

    def test_execute_errors_on_missing_required_answer(self, tmp_path: Path) -> None:
        question = MagicMock()
        question.key = "required_field"
        question.default = None
        question.required = True
        template = MagicMock()
        template.questions.return_value = [question]
        params = CreateNoteParams(zettel_type="note", title="My Note")
        repo = MagicMock()
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )
        result = cmd.execute()

        assert result.success is False
        assert "Missing required answer: required_field" in (result.error or "")

    def test_optional_question_skipped_when_no_answer_or_default(self, tmp_path: Path) -> None:
        """Question with no default, not required, not in extra_answers is skipped."""
        question = MagicMock()
        question.key = "optional_field"
        question.default = None
        question.required = False
        template = MagicMock()
        template.questions.return_value = [question]
        params = CreateNoteParams(zettel_type="note", title="My Note")
        repo = MagicMock()
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )

        with patch("bim.commands.create_note.create_note.CreateZettelUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = tmp_path / "1.md"
            result = cmd.execute()

        assert result.success is True
        call_args = mock_use_case.return_value.execute.call_args
        answers = call_args[0][1]
        assert "optional_field" not in answers

    def test_extra_answers_none_defaults_to_empty(self, tmp_path: Path) -> None:
        """extra_answers=None on params initializes to empty dict."""
        params = CreateNoteParams(zettel_type="note", title="Test", extra_answers=None)
        repo = MagicMock()
        template = MagicMock()
        template.questions.return_value = []
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )
        assert cmd.extra_answers == {}

        with patch("bim.commands.create_note.create_note.CreateZettelUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = tmp_path / "1.md"
            result = cmd.execute()

        assert result.success is True

    def test_execute_no_tags(self, tmp_path: Path) -> None:
        """When tags is None, tags key is not in answers."""
        template = MagicMock()
        template.questions.return_value = []
        params = CreateNoteParams(zettel_type="note", title="My Note", tags=None)
        repo = MagicMock()
        hook_runner = MagicMock()

        cmd = CommandCreateNote(
            params=params,
            path_zettelkasten=tmp_path,
            repo=repo,
            templates={"note": template},
            hook_runner=hook_runner,
        )

        with patch("bim.commands.create_note.create_note.CreateZettelUseCase") as mock_use_case:
            mock_use_case.return_value.execute.return_value = tmp_path / "1.md"
            result = cmd.execute()

        assert result.success is True
        call_args = mock_use_case.return_value.execute.call_args
        answers = call_args[0][1]
        assert "tags" not in answers
