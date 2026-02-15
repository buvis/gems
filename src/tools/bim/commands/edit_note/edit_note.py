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
        paths: list[Path],
        changes: dict[str, Any] | None = None,
        target: str = "metadata",
    ) -> None:
        self.paths = paths
        self.changes = changes
        self.target = target

    def execute(self) -> None:
        if self.changes:
            for path in self.paths:
                if not path.is_file():
                    console.failure(f"{path} doesn't exist")
                    continue
                edit_single(path, self.changes, self.target)
        else:
            from bim.commands.edit_note.tui import EditNoteApp

            app = EditNoteApp(path=self.paths[0])
            app.run()
