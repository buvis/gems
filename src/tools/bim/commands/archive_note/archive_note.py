from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.delete_zettel_use_case import DeleteZettelUseCase
from buvis.pybase.zettel.application.use_cases.update_zettel_use_case import UpdateZettelUseCase

from bim.dependencies import get_repo


def _toggle_archive(
    path: Path,
    destination: Path,
    *,
    archive: bool,
    quiet: bool = False,
) -> str:
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    data = zettel.get_data()

    changes: dict[str, object] = {"processed": archive}
    if data.metadata.get("type") == "project":
        changes["completed"] = archive

    if archive:
        destination.mkdir(parents=True, exist_ok=True)
    dest = destination / path.name
    source = data.file_path
    data.file_path = str(dest)

    UpdateZettelUseCase(repo).execute(zettel, changes)
    data.file_path = source
    DeleteZettelUseCase(repo).execute(zettel)
    action = "Archived" if archive else "Unarchived"
    msg = f"{action} {path.name}"
    if not quiet:
        console.success(msg)
    return msg


def archive_single(path: Path, archive_dir: Path, *, quiet: bool = False) -> str:
    """Archive one zettel: set processed/completed, move to archive_dir."""
    return _toggle_archive(path, archive_dir, archive=True, quiet=quiet)


def unarchive_single(path: Path, zettelkasten_dir: Path) -> str:
    """Unarchive one zettel: clear processed/completed, move back."""
    return _toggle_archive(path, zettelkasten_dir, archive=False)


class CommandArchiveNote:
    def __init__(
        self,
        paths: list[Path],
        path_archive: Path,
        path_zettelkasten: Path,
        *,
        undo: bool = False,
    ) -> None:
        self.paths = paths
        self.path_archive = path_archive
        self.path_zettelkasten = path_zettelkasten
        self.undo = undo

    def execute(self) -> None:
        for path in self.paths:
            if self.undo:
                unarchive_single(path, self.path_zettelkasten)
            else:
                archive_single(path, self.path_archive)
