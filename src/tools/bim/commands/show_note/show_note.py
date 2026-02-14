from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from bim.dependencies import get_repo
from buvis.pybase.zettel import MarkdownZettelFormatter


def show_single(path: Path, *, quiet: bool = False) -> str:
    """Read and format one zettel, return formatted string."""
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    formatted = MarkdownZettelFormatter.format(zettel.get_data())
    if not quiet:
        console.print(formatted, mode="raw")
    return formatted


class CommandShowNote:
    def __init__(self, path: Path) -> None:
        self.path = path

    def execute(self) -> None:
        show_single(self.path)
