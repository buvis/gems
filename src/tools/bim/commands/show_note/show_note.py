from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel import MarkdownZettelFormatter, MarkdownZettelRepository


def show_single(path: Path, *, quiet: bool = False) -> str:
    """Read and format one zettel, return formatted string."""
    repo = MarkdownZettelRepository()
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
