from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.update_zettel_use_case import UpdateZettelUseCase
from bim.dependencies import get_repo


def edit_single(
    path: Path, changes: dict[str, Any], target: str = "metadata", *, quiet: bool = False,
) -> str:
    """Apply changes dict to a zettel and write back."""
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    UpdateZettelUseCase(repo).execute(zettel, changes, target)
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
