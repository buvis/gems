from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel import ReadZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

from bim.dependencies import get_formatter, get_repo


def format_single(path: Path, *, in_place: bool = False, quiet: bool = False) -> str:
    """Format one zettel. Returns formatted content. If in_place, writes back."""
    repo = get_repo()
    reader = ReadZettelUseCase(repo)
    note = reader.execute(str(path))
    formatted = PrintZettelUseCase(get_formatter()).execute(note.get_data())
    if in_place:
        path.write_text(formatted, encoding="utf-8")
        msg = f"Formatted {path.name}"
        if not quiet:
            console.success(msg)
    return formatted


class CommandFormatNote:
    def __init__(
        self,
        paths: list[Path],
        is_highlighting_requested: bool = False,
        is_diff_requested: bool = False,
        path_output: Path | None = None,
    ) -> None:
        self.paths = paths
        self.is_highlighting = is_highlighting_requested
        self.is_printing_diff = is_diff_requested
        self.path_output = path_output.resolve() if path_output else None

    def execute(self) -> None:
        if len(self.paths) > 1:
            for path in self.paths:
                if not path.is_file():
                    console.failure(f"{path} doesn't exist")
                    continue
                format_single(path, in_place=True)
            return

        path = self.paths[0]
        if not path.is_file():
            console.failure(f"{path} doesn't exist")
            return

        original_content = path.read_text()
        formatted_content = format_single(path)

        if self.path_output:
            try:
                self.path_output.write_text(formatted_content, encoding="UTF-8")
            except OSError as e:
                console.panic(f"An error occurred while writing to the file: {e}")
            except UnicodeEncodeError:
                console.panic("The text could not be encoded with UTF-8")

            console.success(f"Formatted note was written to {self.path_output}")

            return

        if self.is_printing_diff and original_content != formatted_content:
            console.print_side_by_side(
                "Original",
                original_content,
                "Formatted",
                formatted_content,
                mode_left="raw",
                mode_right="markdown_with_frontmatter",
            )
        elif self.is_highlighting:
            console.print(formatted_content, mode="markdown_with_frontmatter")
        else:
            console.print(formatted_content, mode="raw")
