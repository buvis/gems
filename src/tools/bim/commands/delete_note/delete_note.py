from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console


def delete_single(path: Path, *, quiet: bool = False) -> str:
    """Permanently delete one zettel file."""
    path.unlink()
    msg = f"Deleted {path.name}"
    if not quiet:
        console.success(msg)
    return msg


class CommandDeleteNote:
    def __init__(self, paths: list[Path], *, force: bool = False) -> None:
        self.paths = paths
        self.force = force

    def execute(self) -> None:
        for path in self.paths:
            if not path.is_file():
                console.failure(f"{path} doesn't exist")
                continue
            if not self.force:
                if not console.confirm(f"Permanently delete {path.name}?"):
                    continue
            delete_single(path)
