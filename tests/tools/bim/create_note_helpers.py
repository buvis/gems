from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from bim.commands.create_note.create_note import CommandCreateNote
from bim.params.create_note import CreateNoteParams
from buvis.pybase.zettel.domain.templates import Hook, Question
from buvis.pybase.zettel.domain.templates.article import ArticleTemplate
from buvis.pybase.zettel.domain.value_objects.zettel_data import ZettelData
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)
from buvis.pybase.zettel.infrastructure.persistence.markdown_zettel_repository.markdown_zettel_repository import (
    MarkdownZettelRepository,
)


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


class TaggedTemplate(NoteTemplate):
    """Contact-like fixture: every note of this template carries ``person``."""

    default_tags = ["person"]


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
    **paths: Path,
) -> CommandCreateNote:
    notes, repo, formatter = scratch_vault
    return CommandCreateNote(
        params=params,
        path_zettelkasten=notes,
        repo=repo,
        templates={"note": template or NoteTemplate()},
        hook_runner=hook_runner,
        formatter=formatter,
        **paths,
    )


def write_contact(notes: Path, slug: str, title: str) -> None:
    (notes / "contact").mkdir(exist_ok=True)
    (notes / "contact" / f"{slug}.md").write_text(f"---\ntitle: {title}\ntype: contact\n---\n\n# {title}\n")


def article_command(scratch_vault: ScratchVault, tmp_path: Path, params: CreateNoteParams) -> CommandCreateNote:
    notes, repo, formatter = scratch_vault
    (tmp_path / "archives").mkdir(exist_ok=True)
    return CommandCreateNote(
        params=params,
        path_zettelkasten=notes,
        repo=repo,
        templates={"article": ArticleTemplate()},
        hook_runner=None,
        formatter=formatter,
        path_articles=tmp_path / "archives" / "articles",
    )
