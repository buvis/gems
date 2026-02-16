from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

from bim.dependencies import get_formatter, get_repo


def show_single(path: Path, *, quiet: bool = False) -> str:
    """Read and format one zettel, return formatted string."""
    repo = get_repo()
    zettel = repo.find_by_location(str(path))
    formatted = PrintZettelUseCase(get_formatter()).execute(zettel.get_data())
    if not quiet:
        console.print(formatted, mode="raw")
    return formatted


class CommandShowNote:
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths

    def execute(self) -> None:
        for i, path in enumerate(self.paths):
            if not path.is_file():
                console.failure(f"{path} doesn't exist")
                continue
            if i > 0:
                console.print("---", mode="raw")
            show_single(path)
