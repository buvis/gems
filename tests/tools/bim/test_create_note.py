from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest
from bim.commands.create_note.create_note import CommandCreateNote
from bim.note_write_cli import create_note
from bim.params.create_note import CreateNoteParams
from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
)
from click.testing import CliRunner


class TestCreateNoteCli:
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
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
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
                formatter=mock_get_formatter.return_value,
            )
            instance.execute.assert_called_once_with()

    def test_create_note_tags_and_answers(self, runner: CliRunner) -> None:
        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
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
                formatter=mock_get_formatter.return_value,
            )
            instance.execute.assert_called_once_with()

    def test_create_note_without_type_or_title_launches_tui(self, runner: CliRunner) -> None:
        with (
            patch("bim.note_write_cli.get_settings") as mock_settings,
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
            patch("bim.note_write_cli.get_settings") as mock_settings,
            patch("bim.commands.create_note.create_note.CommandCreateNote") as mock_cmd,
            patch("bim.note_write_cli.console") as mock_console,
            patch("bim.dependencies.get_repo") as mock_get_repo,
            patch("bim.dependencies.get_templates") as mock_get_templates,
            patch("bim.dependencies.get_hook_runner") as mock_get_hook_runner,
            patch("bim.dependencies.get_formatter") as mock_get_formatter,
        ):
            mock_settings.return_value = MagicMock(path_zettelkasten="/tmp/zk")
            mock_get_repo.return_value = MagicMock()
            mock_get_templates.return_value = MagicMock()
            mock_get_hook_runner.return_value = MagicMock()
            mock_get_formatter.return_value = MagicMock()
            mock_cmd.side_effect = FileNotFoundError("missing template")

            result = runner.invoke(create_note, ["-t", "note", "--title", "X"], catch_exceptions=False)

            assert result.exit_code == 0
            mock_console.panic.assert_called_once_with("missing template")


class NoteTemplate:
    """Public template fixture that records answers and emits distinct content."""

    name = "note"
    body_section = "# Content"

    def __init__(self, questions: list[Question] | None = None, hooks: list[Hook] | None = None) -> None:
        self.prompts = questions or []
        self.hook_list = hooks or []
        self.answers: dict[str, Any] = {}

    def questions(self) -> list[Question]:
        return self.prompts

    def build_data(self, answers: dict[str, Any]) -> ZettelData:
        self.answers = answers.copy()
        tags = str(answers.get("tags", "")).split(",")
        return ZettelData(
            metadata={
                "type": "note",
                "title": answers["title"],
                "tags": [tag for tag in tags if tag],
            },
            sections=[("# Content", "Template default"), ("# Details", "Keep this section")],
        )

    def hooks(self) -> list[Hook]:
        return self.hook_list


class LabeledFormatter(MarkdownZettelFormatter):
    @staticmethod
    def format(zettel_data: ZettelData) -> str:
        return "Formatter dependency\n" + MarkdownZettelFormatter.format(zettel_data)


ScratchVault = tuple[Path, MarkdownZettelRepository, MarkdownZettelFormatter]


def create_symlink(path: Path, target: Path, *, target_is_directory: bool = False) -> None:
    try:
        path.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"symlink fixture unavailable: {error}")


@pytest.fixture
def scratch_vault(tmp_path: Path) -> ScratchVault:
    notes = tmp_path / "vault" / "notes"
    notes.mkdir(parents=True)
    (notes.parent / "inbox").mkdir()
    return notes, MarkdownZettelRepository(notes), MarkdownZettelFormatter()


def create_command(
    scratch_vault: ScratchVault,
    params: CreateNoteParams,
    template: NoteTemplate | None = None,
    hook_runner: Any = None,
) -> CommandCreateNote:
    notes, repo, formatter = scratch_vault
    return CommandCreateNote(
        params=params,
        path_zettelkasten=notes,
        repo=repo,
        templates={"note": template or NoteTemplate()},
        hook_runner=hook_runner,
        formatter=formatter,
    )


class TestCommandCreateNote:
    def test_raises_when_zettelkasten_dir_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            CommandCreateNote(
                params=CreateNoteParams(zettel_type="note", title="Test"),
                path_zettelkasten=tmp_path / "missing",
                repo=MagicMock(),
                templates={},
                hook_runner=None,
                formatter=MarkdownZettelFormatter(),
            )

    @pytest.mark.parametrize(
        ("zettel_type", "title", "error"),
        [
            (None, "Test", "zettel_type and title are required"),
            ("note", None, "zettel_type and title are required"),
            ("notebook", "Test", "Unknown template: notebook"),
            ("other", "Test", "Unknown template: other"),
        ],
    )
    def test_invalid_required_inputs_create_no_note(
        self, scratch_vault: ScratchVault, zettel_type: str | None, title: str | None, error: str
    ) -> None:
        result = create_command(scratch_vault, CreateNoteParams(zettel_type=zettel_type, title=title)).execute()

        assert result.success is False
        assert result.error == error
        assert list(scratch_vault[0].iterdir()) == []

    @pytest.mark.parametrize("title,tags", [("My Note", "a,b"), ("Other Topic", "work/home,équipe")])
    def test_metadata_has_relative_path_and_wikilink(self, scratch_vault: ScratchVault, title: str, tags: str) -> None:
        notes, repo, formatter = scratch_vault
        params = CreateNoteParams(zettel_type="note", title=title, tags=tags, body="First\n\nSecond")

        result = create_command(scratch_vault, params).execute()

        assert result.success is True
        path = Path(result.metadata["path"])
        saved = repo.find_by_location(str(path))
        relative_path = path.relative_to(notes.parent).as_posix()
        assert path.parent == notes.resolve()
        assert result.output == f"Created {path}"
        assert result.metadata == {
            "id": str(saved.id),
            "type": "note",
            "title": title,
            "tags": sorted(tags.split(",")),
            "path": str(path.resolve()),
            "relative_path": relative_path,
            "wikilink": f"[[{relative_path[:-3]}|{title}]]",
        }
        assert saved.title == title
        assert saved.tags == sorted(tags.split(","))
        assert saved.id is not None
        assert str(saved.id) == path.stem
        assert "First\n\nSecond" in formatter.format(saved.get_data())
        assert "Keep this section" in path.read_text()
        json.dumps(result.metadata)

    @pytest.mark.parametrize(
        "tags,invalid",
        [
            ("good,##hash", "#hash"),
            ("good,with space", "with space"),
            ("a#b", "a#b"),
            ("12/34", "12/34"),
            ("a//b", "a//b"),
            ("a.b", "a.b"),
        ],
    )
    def test_rejects_tag_with_hash_or_space(self, scratch_vault: ScratchVault, tags: str, invalid: str) -> None:
        template = NoteTemplate()
        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Test", tags=tags),
            template,
        ).execute()

        assert result.success is False
        assert result.error == f"invalid tag '{invalid}': use letters, digits, '-', '_', and '/' for nesting"
        assert template.answers == {}
        assert list(scratch_vault[0].iterdir()) == []

    @pytest.mark.parametrize(
        "tags,expected",
        [
            (" #Work ,work,OTHER,work, ", "work,other"),
            ("Équipe/Sous_1,équipe/sous_1,#two-2,2two", "équipe/sous_1,two-2,2two"),
            (" , , ", ""),
        ],
    )
    def test_dedupes_tags_case_insensitively(self, scratch_vault: ScratchVault, tags: str, expected: str) -> None:
        template = NoteTemplate()
        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Test", tags=tags),
            template,
        ).execute()

        assert result.success is True
        assert template.answers["tags"] == expected
        assert result.metadata["tags"] == (sorted(expected.split(",")) if expected else [])

    def test_tag_question_does_not_override_validated_tags(self, scratch_vault: ScratchVault) -> None:
        template = NoteTemplate([Question("tags", "Tags", default="bad tag", required=True)])
        params = CreateNoteParams(
            zettel_type="note",
            title="Test",
            tags="#WORK,work,Home",
            extra_answers={"tags": "also bad"},
        )

        result = create_command(scratch_vault, params, template).execute()

        assert result.success is True
        assert template.answers["tags"] == "work,home"
        assert result.metadata["tags"] == ["home", "work"]

    @pytest.mark.parametrize("extra_answers", [None, {}])
    def test_omitted_tags_and_optional_answers_stay_omitted(
        self, scratch_vault: ScratchVault, extra_answers: dict[str, str] | None
    ) -> None:
        template = NoteTemplate([Question("optional_field", "Optional")])
        params = CreateNoteParams(zettel_type="note", title="Test", extra_answers=extra_answers)

        result = create_command(scratch_vault, params, template).execute()

        assert result.success is True
        assert template.answers == {"title": "Test"}
        assert result.metadata["tags"] == []

    @pytest.mark.parametrize("project,priority", [("alpha", "low"), ("beta", "high")])
    def test_extra_answers_and_question_defaults_reach_template(
        self, scratch_vault: ScratchVault, project: str, priority: str
    ) -> None:
        template = NoteTemplate(
            [
                Question("project", "Project", required=True),
                Question("priority", "Priority", default=priority),
            ]
        )
        params = CreateNoteParams(zettel_type="note", title="Test", extra_answers={"project": project})

        result = create_command(scratch_vault, params, template).execute()

        assert result.success is True
        assert template.answers == {"title": "Test", "project": project, "priority": priority}

    def test_missing_required_answer_prevents_save(self, scratch_vault: ScratchVault) -> None:
        template = NoteTemplate([Question("required_field", "Required", required=True)])

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", title="Test"), template).execute()

        assert result.success is False
        assert result.error == "Missing required answer: required_field"
        assert list(scratch_vault[0].iterdir()) == []

    @pytest.mark.parametrize("relative", ["outside.md", "inbox-copy/item.md", "inbox/item.txt", "inbox/missing.md"])
    def test_source_outside_inbox_is_rejected(self, scratch_vault: ScratchVault, relative: str) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        if source.name != "missing.md":
            source.write_text("Source content")
        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", source=source),
        ).execute()

        assert result.success is False
        assert result.error == f"--source must be a Markdown file inside {notes.parent}/inbox"
        assert list(notes.iterdir()) == []
        assert not (notes.parent / ".trash").exists()
        if source.name != "missing.md":
            assert source.read_text() == "Source content"

    def test_source_directory_with_markdown_suffix_is_rejected(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "directory.md"
        source.mkdir()

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is False
        assert result.error == f"--source must be a Markdown file inside {notes.parent}/inbox"
        assert list(notes.iterdir()) == []

    @pytest.mark.parametrize("symlink_inbox", [False, True])
    def test_source_symlinks_cannot_escape_vault(
        self, scratch_vault: ScratchVault, tmp_path: Path, symlink_inbox: bool
    ) -> None:
        notes, _, _ = scratch_vault
        outside = tmp_path / "outside"
        outside.mkdir()
        original = outside / "same.md"
        original.write_text("Do not move this")
        inbox = notes.parent / "inbox"
        source = inbox / "same.md"
        if symlink_inbox:
            inbox.rmdir()
            create_symlink(inbox, outside, target_is_directory=True)
        else:
            create_symlink(source, original)

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is False
        assert result.error == f"--source must be a Markdown file inside {notes.parent}/inbox"
        assert original.read_text() == "Do not move this"
        assert list(notes.iterdir()) == []
        assert not (notes.parent / ".trash").exists()

    @pytest.mark.parametrize(
        "title,filename,expected",
        [
            (None, "Inbox Subject.md", "Inbox Subject"),
            ("Explicit Subject", "Different Name.md", "Explicit Subject"),
        ],
    )
    def test_source_frontmatter_is_stripped_and_file_trashed(
        self, scratch_vault: ScratchVault, title: str | None, filename: str, expected: str
    ) -> None:
        notes, repo, formatter = scratch_vault
        source = notes.parent / "inbox" / filename
        original = "---\r\ntitle: Discarded\r\ntags: [discarded]\r\n---\r\nFirst\r\n\r\nSecond\r\n"
        source.write_bytes(original.encode())
        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title=title, source=source),
        ).execute()

        assert result.success is True
        assert result.metadata["title"] == expected
        assert result.metadata["tags"] == []
        saved = repo.find_by_location(result.metadata["path"])
        content = formatter.format(saved.get_data())
        assert "First\n\nSecond" in content
        assert "Discarded" not in content
        assert "discarded" not in content
        assert "\r" not in content
        assert not source.exists()
        destination = notes.parent / ".trash" / filename
        assert result.metadata["trashed_source"] == str(destination)
        assert destination.read_bytes() == original.encode()
        assert "errors" not in result.metadata

    def test_source_strips_only_one_leading_frontmatter_block(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "Two Blocks.md"
        source.write_text("---\ntitle: Remove me\n---\n---\nkeep: this\n---\nBody\n")

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is True
        content = Path(result.metadata["path"]).read_text()
        assert "Remove me" not in content
        assert "---\nkeep: this\n---\nBody" in content

    def test_source_trash_uses_next_available_name_without_overwriting(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "Topic.md"
        source.write_text("New content")
        trash = notes.parent / ".trash"
        trash.mkdir()
        first, second = trash / "Topic.md", trash / "Topic 1.md"
        first.write_text("Old first")
        second.write_text("Old second")

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is True
        assert result.metadata["trashed_source"] == str(trash / "Topic 2.md")
        assert (trash / "Topic 2.md").read_text() == "New content"
        assert first.read_text() == "Old first"
        assert second.read_text() == "Old second"
        assert not source.exists()

    @pytest.mark.parametrize("body", ["", "Supplied body"])
    def test_body_and_source_are_mutually_exclusive_before_reading_source(
        self, scratch_vault: ScratchVault, body: str
    ) -> None:
        source = scratch_vault[0].parent / "inbox" / "missing.md"

        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Test", body=body, source=source),
        ).execute()

        assert result.success is False
        assert result.error
        assert "body" in result.error.lower()
        assert "source" in result.error.lower()
        assert result.error != f"--source must be a Markdown file inside {source.parent}"
        assert list(scratch_vault[0].iterdir()) == []

    @pytest.mark.parametrize("from_source", [False, True])
    def test_dry_run_writes_nothing_and_returns_content(self, scratch_vault: ScratchVault, from_source: bool) -> None:
        notes, repo, _ = scratch_vault
        scratch_vault = notes, repo, LabeledFormatter()
        source = notes.parent / "inbox" / "Dry Source.md"
        source.write_text("---\ntitle: Ignore this\n---\nPreview body\n")
        params = CreateNoteParams(
            zettel_type="note",
            title="Preview Note" if from_source else "Other Preview",
            source=source if from_source else None,
            body=None if from_source else "Other body",
            tags="Preview,preview,Other",
            dry_run=True,
        )
        before = sorted(str(path) for path in notes.parent.rglob("*"))

        def unexpected_hook(*args: Any) -> None:
            pytest.fail("dry run executed a hook")

        template = NoteTemplate(hooks=[Hook("preview")])
        result = create_command(scratch_vault, params, template, hook_runner=unexpected_hook).execute()

        assert result.success is True
        metadata = result.metadata
        assert metadata["dry_run"] is True
        assert metadata["title"] == params.title
        assert metadata["tags"] == ["other", "preview"]
        assert metadata["type"] == "note"
        assert metadata["id"] == Path(metadata["path"]).stem
        assert Path(metadata["path"]).parent == notes
        assert metadata["relative_path"] == f"notes/{metadata['id']}.md"
        assert metadata["wikilink"] == f"[[notes/{metadata['id']}|{params.title}]]"
        assert ("Preview body" if from_source else "Other body") in metadata["content"]
        assert metadata["content"].startswith("Formatter dependency\n")
        assert "Keep this section" in metadata["content"]
        assert "Ignore this" not in metadata["content"]
        assert "trashed_source" not in metadata
        assert "date" not in metadata
        assert sorted(str(path) for path in notes.parent.rglob("*")) == before
        assert list(notes.iterdir()) == []
        assert source.read_text() == "---\ntitle: Ignore this\n---\nPreview body\n"
        json.dumps(metadata)

    def test_invalid_utf8_source_returns_failure_without_moving_source(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "Broken.md"
        source.write_bytes(b"\xff\xfe")

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is False
        assert result.error
        assert source.read_bytes() == b"\xff\xfe"
        assert list(notes.iterdir()) == []
        assert not (notes.parent / ".trash").exists()

    @pytest.mark.parametrize("error_type", [OSError, FileExistsError])
    def test_save_failure_returns_error_without_trashing_source(
        self, scratch_vault: ScratchVault, error_type: type[OSError]
    ) -> None:
        notes, repo, _ = scratch_vault
        source = notes.parent / "inbox" / "Retained.md"
        source.write_text("Keep source")
        with patch.object(repo, "save", autospec=True, side_effect=error_type("disk full")):
            result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is False
        assert "disk full" in (result.error or "")
        assert source.read_text() == "Keep source"
        assert list(notes.iterdir()) == []
        assert not (notes.parent / ".trash").exists()

    def test_readback_failure_reports_saved_note_and_retains_source(self, scratch_vault: ScratchVault) -> None:
        notes, repo, _ = scratch_vault
        source = notes.parent / "inbox" / "Retained.md"
        source.write_text("Keep source")
        with patch.object(repo, "find_by_location", autospec=True, side_effect=OSError("cannot read back")):
            result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        saved_paths = list(notes.glob("*.md"))
        assert len(saved_paths) == 1
        assert result.success is False
        assert result.error == f"note saved at {saved_paths[0]}, but metadata failed: cannot read back"
        assert "Keep source" in saved_paths[0].read_text()
        assert source.read_text() == "Keep source"
        assert not (notes.parent / ".trash").exists()

    def test_trash_move_failure_keeps_success_and_reports_cleanup_error(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "Retained.md"
        source.write_text("Keep source")
        with patch("os.link", autospec=True, side_effect=OSError("cross-device move")):
            result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is True
        assert Path(result.metadata["path"]).is_file()
        assert "Keep source" in Path(result.metadata["path"]).read_text()
        assert source.read_text() == "Keep source"
        assert "trashed_source" not in result.metadata
        assert isinstance(result.metadata["errors"], list)
        assert any("cross-device move" in error for error in result.metadata["errors"])

    def test_exhausted_trash_candidates_retain_source_and_saved_note(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "Retained.md"
        source.write_text("Keep source")
        trash = notes.parent / ".trash"
        candidates: list[Path] = []

        def collide(source_path: Path, destination: Path) -> None:
            candidates.append(Path(destination))
            raise FileExistsError("trash candidate exists")

        with patch("os.link", autospec=True, side_effect=collide):
            result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert candidates == [trash / "Retained.md", *[trash / f"Retained {index}.md" for index in range(1, 1000)]]
        assert result.success is True
        assert "Keep source" in Path(result.metadata["path"]).read_text()
        assert source.read_text() == "Keep source"
        assert "trashed_source" not in result.metadata
        assert isinstance(result.metadata["errors"], list)
        assert result.metadata["errors"]
        assert list(trash.iterdir()) == []

    def test_failed_source_unlink_preserves_source_and_trash_link(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "Retained.md"
        source.write_text("Keep source")
        destination = notes.parent / ".trash" / source.name
        original_unlink = Path.unlink

        def fail_source_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
            if path == source:
                raise OSError("source unlink denied")
            original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", autospec=True, side_effect=fail_source_unlink):
            result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is True
        assert "Keep source" in Path(result.metadata["path"]).read_text()
        assert source.read_text() == "Keep source"
        assert destination.read_text() == "Keep source"
        assert source.samefile(destination)
        assert "trashed_source" not in result.metadata
        assert isinstance(result.metadata["errors"], list)
        errors = "\n".join(result.metadata["errors"])
        assert "source unlink denied" in errors
        assert str(source) in errors
        assert str(destination) in errors

    def test_metadata_uses_saved_readback_after_hook_changes_note(self, scratch_vault: ScratchVault) -> None:
        notes, repo, _ = scratch_vault
        called_roots: list[Path] = []

        def update_saved_note(hooks: list[Hook], data: ZettelData, root: Path) -> None:
            assert [hook.name for hook in hooks] == ["retitle"]
            assert data.metadata["title"] == "Before Save"
            called_roots.append(root)
            saved = repo.find_by_location(str(next(root.glob("*.md"))))
            updated = saved.get_data()
            updated.metadata["title"] = "After Hook"
            repo.save(Zettel(updated))

        template = NoteTemplate(hooks=[Hook("retitle")])
        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Before Save"),
            template,
            hook_runner=update_saved_note,
        ).execute()

        assert result.success is True
        assert called_roots == [notes.resolve()]
        saved = repo.find_by_location(result.metadata["path"])
        assert saved.title == "After Hook"
        assert result.metadata["title"] == saved.title
        assert result.metadata["wikilink"].endswith("|After Hook]]")

    def test_hook_failure_reports_saved_path_and_retains_source(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "Retained.md"
        source.write_text("Keep source")

        def fail_hook(hooks: list[Hook], data: ZettelData, root: Path) -> None:
            raise ValueError("hook exploded")

        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", source=source),
            NoteTemplate(hooks=[Hook("failure")]),
            hook_runner=fail_hook,
        ).execute()

        saved_paths = list(notes.glob("*.md"))
        assert len(saved_paths) == 1
        assert result.success is False
        assert result.error == f"note saved at {saved_paths[0]}, but hook failed: hook exploded"
        assert "Keep source" in saved_paths[0].read_text()
        assert source.read_text() == "Keep source"
        assert not (notes.parent / ".trash").exists()

    @pytest.mark.parametrize(
        "body,expected",
        [
            ("", "Template default"),
            (" \t\r\n\r\n", "Template default"),
            ("Body alpha", "Template default\n\nBody alpha"),
            ("Body beta", "Template default\n\nBody beta"),
            ("\r\n \t\r\n  Body\r\n  indented\r\n\r\n", "Template default\n\n  Body\n  indented"),
        ],
    )
    def test_explicit_body_appends_to_template_and_blank_body_preserves_content(
        self, scratch_vault: ScratchVault, body: str, expected: str
    ) -> None:
        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Test", body=body),
        ).execute()

        assert result.success is True
        saved = scratch_vault[1].find_by_location(result.metadata["path"])
        assert saved.get_data().sections == [("# Test", expected), ("# Details", "Keep this section")]

    def test_trash_symlink_outside_vault_is_reported_after_save(
        self, scratch_vault: ScratchVault, tmp_path: Path
    ) -> None:
        notes, _, _ = scratch_vault
        outside = tmp_path / "outside-trash"
        outside.mkdir()
        create_symlink(notes.parent / ".trash", outside, target_is_directory=True)
        source = notes.parent / "inbox" / "Retained.md"
        source.write_text("Keep source")

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is True
        assert Path(result.metadata["path"]).is_file()
        assert source.read_text() == "Keep source"
        assert list(outside.iterdir()) == []
        assert "trashed_source" not in result.metadata
        assert result.metadata["errors"]
