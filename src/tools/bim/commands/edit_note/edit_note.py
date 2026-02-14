from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.adapters import console
from buvis.pybase.zettel import MarkdownZettelFormatter, MarkdownZettelRepository


def edit_single(
    path: Path, changes: dict[str, Any], target: str = "metadata", *, quiet: bool = False,
) -> str:
    """Apply changes dict to a zettel and write back."""
    repo = MarkdownZettelRepository()
    zettel = repo.find_by_location(str(path))
    data = zettel.get_data()

    if target == "section":
        for field, value in changes.items():
            replaced = False
            new_sections = []
            for heading, old_body in data.sections:
                if heading == field:
                    new_sections.append((heading, value))
                    replaced = True
                else:
                    new_sections.append((heading, old_body))
            if not replaced:
                new_sections.append((field, value))
            data.sections = new_sections
    elif target == "reference":
        data.reference.update(changes)
    else:
        data.metadata.update(changes)

    formatted = MarkdownZettelFormatter.format(data)
    path.write_text(formatted, encoding="utf-8")
    msg = f"Updated {path.name}"
    if not quiet:
        console.success(msg)
    return msg


class CommandEditNote:
    def __init__(
        self,
        path: Path,
        changes: dict[str, Any] | None = None,
        target: str = "metadata",
    ) -> None:
        self.path = path
        self.changes = changes
        self.target = target

    def execute(self) -> None:
        if self.changes:
            edit_single(self.path, self.changes, self.target)
        else:
            from bim.commands.edit_note.tui import EditNoteApp

            app = EditNoteApp(path=self.path)
            app.run()
