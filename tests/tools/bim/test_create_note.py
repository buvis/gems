from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bim.commands.create_note.create_note import CommandCreateNote
from bim.params.create_note import CreateNoteParams
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)

from tests.tools.bim.create_note_helpers import (
    LabeledFormatter,
    NoteTemplate,
    ScratchVault,
    TaggedTemplate,
    create_command,
    create_symlink,
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
        notes, repo, _ = scratch_vault
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
        assert path.read_text().endswith(
            f"\n# {title}\n\nTemplate default  \n\nFirst  \n\nSecond  \n\n# Details\n\nKeep this section  \n\n---"
        )
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
            ("Ⅳ,²/Ⅳ", "ⅳ,²/ⅳ"),
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

    @pytest.mark.parametrize(
        "relative", ["outside.md", "inbox-copy/item.md", "inbox/item.txt", "inbox/item.MD", "inbox/missing.md"]
    )
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
        notes, repo, _ = scratch_vault
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
        assert saved.title == expected
        assert saved.tags == []
        content = Path(result.metadata["path"]).read_text()
        assert content.endswith(
            f"\n# {expected}\n\nTemplate default  \n\nFirst  \n\nSecond  \n\n# Details\n\nKeep this section  \n\n---"
        )
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
        assert "---  \nkeep: this  \n---  \nBody  \n\n# Details\n\nKeep this section  \n\n---" in content

    def test_source_frontmatter_closing_at_eof_remains_body_content(self, scratch_vault: ScratchVault) -> None:
        notes, _, _ = scratch_vault
        source = notes.parent / "inbox" / "EOF.md"
        original = "---\ntitle: Keep me\n---"
        source.write_text(original)

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", source=source)).execute()

        assert result.success is True
        assert (
            Path(result.metadata["path"])
            .read_text()
            .endswith(
                "\n# EOF\n\nTemplate default  \n\n---  \ntitle: Keep me  \n---  \n\n"
                "# Details\n\nKeep this section  \n\n---"
            )
        )
        assert not source.exists()
        assert Path(result.metadata["trashed_source"]).read_text() == original

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

    def test_hook_changes_land_in_saved_note_metadata_and_warnings(self, scratch_vault: ScratchVault) -> None:
        notes, repo, _ = scratch_vault
        called_roots: list[Path] = []

        def retitle_before_save(hooks: list[Hook], data: ZettelData, root: Path) -> list[str]:
            assert [hook.name for hook in hooks] == ["retitle"]
            assert data.metadata["title"] == "Before Save"
            assert next(root.glob("*.md")).read_bytes() == b""
            called_roots.append(root)
            data.metadata["title"] = "After Hook"
            return ["resources folder skipped"]

        template = NoteTemplate(hooks=[Hook("retitle")])
        result = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="Before Save"),
            template,
            hook_runner=retitle_before_save,
        ).execute()

        assert result.success is True
        assert called_roots == [notes.resolve()]
        saved = repo.find_by_location(result.metadata["path"])
        assert saved.title == "After Hook"
        assert result.metadata["title"] == saved.title
        assert result.metadata["wikilink"].endswith("|After Hook]]")
        assert result.warnings == ["resources folder skipped"]

    def test_metadata_returns_empty_tags_when_saved_readback_has_none(self, scratch_vault: ScratchVault) -> None:
        _, repo, _ = scratch_vault
        readback = repo.find_by_location

        class UntaggedReadback:
            tags = None

            def __init__(self, saved: Zettel) -> None:
                self.saved = saved

            def __getattr__(self, name: str) -> Any:
                return getattr(self.saved, name)

        def without_tags(location: str) -> UntaggedReadback:
            return UntaggedReadback(readback(location))

        with patch.object(repo, "find_by_location", side_effect=without_tags):
            result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", title="Test")).execute()

        assert result.success is True
        saved = readback(result.metadata["path"])
        assert result.metadata["tags"] == []
        assert result.metadata["id"] == str(saved.id)
        assert result.metadata["title"] == saved.title
        assert result.metadata["type"] == saved.get_data().metadata["type"]
        json.dumps(result.metadata)

    def test_hook_failure_writes_nothing_and_retains_source(self, scratch_vault: ScratchVault) -> None:
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

        assert result.success is False
        assert result.error == "hook failed: hook exploded"
        assert list(notes.iterdir()) == []
        assert source.read_text() == "Keep source"
        assert not (notes.parent / ".trash").exists()

    def test_default_tags_come_first(self, scratch_vault: ScratchVault) -> None:
        template = TaggedTemplate()

        result = create_command(
            scratch_vault, CreateNoteParams(zettel_type="note", title="Ada", tags="Work,#person"), template
        ).execute()

        assert result.success is True
        assert template.answers["tags"] == "person,work"
        assert result.metadata["tags"] == ["person", "work"]

    def test_default_tags_apply_when_no_tags_are_given(self, scratch_vault: ScratchVault) -> None:
        template = TaggedTemplate()

        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", title="Ada"), template).execute()

        assert result.success is True
        assert template.answers["tags"] == "person"
        assert result.metadata["tags"] == ["person"]

    def test_reserved_tag_of_other_template_is_rejected(self, scratch_vault: ScratchVault) -> None:
        notes, repo, formatter = scratch_vault
        plain = NoteTemplate()

        result = CommandCreateNote(
            params=CreateNoteParams(zettel_type="note", title="T", tags="person"),
            path_zettelkasten=notes,
            repo=repo,
            templates={"note": plain, "contact": TaggedTemplate()},
            hook_runner=None,
            formatter=formatter,
        ).execute()

        assert result.success is False
        assert result.error == "tag 'person' is reserved for the contact template"
        assert plain.answers == {}
        assert list(notes.iterdir()) == []

    def test_inherited_default_tag_is_not_reserved_for_the_child_template(self, scratch_vault: ScratchVault) -> None:
        notes, repo, formatter = scratch_vault
        colleague = TaggedTemplate()

        result = CommandCreateNote(
            params=CreateNoteParams(zettel_type="colleague", title="Ada", tags="person,work"),
            path_zettelkasten=notes,
            repo=repo,
            templates={"contact": TaggedTemplate(), "colleague": colleague},
            hook_runner=None,
            formatter=formatter,
        ).execute()

        assert result.success is True
        assert colleague.answers["tags"] == "person,work"

    @pytest.mark.parametrize(
        "body,expected",
        [
            ("", "Template default  "),
            (" \t\r\n\r\n", "Template default  "),
            ("Body alpha", "Template default  \n\nBody alpha  "),
            ("Body beta", "Template default  \n\nBody beta  "),
            ("\r\n \t\r\n  Body\r\n  indented\r\n\r\n", "Template default  \n\n  Body  \n  indented  "),
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
        assert (
            Path(result.metadata["path"])
            .read_text()
            .endswith(f"\n# Test\n\n{expected}\n\n# Details\n\nKeep this section  \n\n---")
        )

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


class TestReviewRegressions:
    def test_note_mode_matches_sibling(self, scratch_vault: ScratchVault) -> None:
        sibling = scratch_vault[0] / "sibling.md"
        sibling.write_text("existing")
        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", title="Test")).execute()
        assert result.success
        assert Path(result.metadata["path"]).stat().st_mode == sibling.stat().st_mode

    def test_folder_cannot_escape_notes(self, scratch_vault: ScratchVault) -> None:
        template = NoteTemplate()
        template.folder = "../outside"
        result = create_command(scratch_vault, CreateNoteParams(zettel_type="note", title="Test"), template).execute()
        assert not result.success
        assert not (scratch_vault[0].parent / "outside").exists()

    @pytest.mark.parametrize("value", ["", "   ", "online"])
    def test_required_and_choice_answers_are_validated(self, scratch_vault: ScratchVault, value: str) -> None:
        template = NoteTemplate(questions=[Question(key="location", prompt="Where?", required=True, choices=["home"])])
        result = create_command(
            scratch_vault, CreateNoteParams(zettel_type="note", title="T", extra_answers={"location": value}), template
        ).execute()
        assert not result.success
        assert list(scratch_vault[0].iterdir()) == []

    @pytest.mark.parametrize("from_default", [False, True])
    @pytest.mark.parametrize("value", ["#Work", "123", "person"])
    def test_question_tags_use_tag_validation(
        self, scratch_vault: ScratchVault, value: str, from_default: bool
    ) -> None:
        template = NoteTemplate(
            questions=[Question(key="tags", prompt="Tags?", default=value if from_default else None)]
        )
        cmd = create_command(
            scratch_vault,
            CreateNoteParams(zettel_type="note", title="T", extra_answers={} if from_default else {"tags": value}),
            template,
        )
        cmd.templates["contact"] = TaggedTemplate()
        result = cmd.execute()
        if value == "#Work":
            assert result.success
            assert template.answers["tags"] == "work"
        else:
            assert not result.success

    def test_unexpected_exception_returns_failure(self, scratch_vault: ScratchVault) -> None:
        cmd = create_command(scratch_vault, CreateNoteParams(zettel_type="note", title="T"))
        with patch.object(cmd, "_execute", side_effect=TypeError("unexpected")):
            result = cmd.execute()
        assert not result.success
        assert result.error == "unexpected"
