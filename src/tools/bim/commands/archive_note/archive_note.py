from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from bim.dependencies import get_repo
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import MarkdownZettelFormatter


def archive_single(path: Path, archive_dir: Path, *, quiet: bool = False) -> str:
    """Archive one zettel: set processed/completed, move to archive_dir."""
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    data = zettel.get_data()

    data.metadata["processed"] = True
    if data.metadata.get("type") == "project":
        data.metadata["completed"] = True

    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / path.name
    formatted = MarkdownZettelFormatter.format(data)
    dest.write_text(formatted, encoding="utf-8")
    path.unlink()
    msg = f"Archived {path.name}"
    if not quiet:
        console.success(msg)
    return msg


def unarchive_single(path: Path, zettelkasten_dir: Path) -> str:
    """Unarchive one zettel: clear processed/completed, move back."""
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    data = zettel.get_data()

    data.metadata["processed"] = False
    if data.metadata.get("type") == "project":
        data.metadata["completed"] = False

    dest = zettelkasten_dir / path.name
    formatted = MarkdownZettelFormatter.format(data)
    dest.write_text(formatted, encoding="utf-8")
    path.unlink()
    msg = f"Unarchived {path.name}"
    console.success(msg)
    return msg


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
