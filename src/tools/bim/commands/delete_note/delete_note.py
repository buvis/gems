from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.delete_zettel_use_case import DeleteZettelUseCase

from bim.dependencies import get_repo


def delete_single(path: Path, *, quiet: bool = False) -> str:
    """Permanently delete one zettel file."""
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    DeleteZettelUseCase(repo).execute(zettel)
    msg = f"Deleted {path.name}"
    if not quiet:
        console.success(msg)
    return msg


class CommandDeleteNote:
    def __init__(self, paths: list[Path], *, force: bool = False, batch: bool = False) -> None:
        self.paths = paths
        self.force = force
        self.batch = batch

    def execute(self) -> None:
        if self.batch and not self.force:
            if not console.confirm(f"Permanently delete {len(self.paths)} zettels?"):
                return

        for path in self.paths:
            if not path.is_file():
                console.failure(f"{path} doesn't exist")
                continue
            if not self.force and not self.batch:
                if not console.confirm(f"Permanently delete {path.name}?"):
                    continue
            delete_single(path)
