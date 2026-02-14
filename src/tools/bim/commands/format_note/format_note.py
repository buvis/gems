from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel import (
    MarkdownZettelFormatter,
    MarkdownZettelRepository,
    ReadZettelUseCase,
)


def format_single(path: Path, *, in_place: bool = False, quiet: bool = False) -> str:
    """Format one zettel. Returns formatted content. If in_place, writes back."""
    repo = MarkdownZettelRepository()
    reader = ReadZettelUseCase(repo)
    formatter = MarkdownZettelFormatter()
    note = reader.execute(str(path))
    formatted = formatter.format(note.get_data())
    if in_place:
        path.write_text(formatted, encoding="utf-8")
        msg = f"Formatted {path.name}"
        if not quiet:
            console.success(msg)
    return formatted


class CommandFormatNote:
    def __init__(
        self,
        path_note: Path,
        is_highlighting_requested: bool = False,
        is_diff_requested: bool = False,
        path_output: Path | None = None,
    ) -> None:
        if not path_note.is_file():
            raise FileNotFoundError(f"Note not found: {path_note}")
        self.path_note = path_note
        self.is_highlighting = is_highlighting_requested
        self.is_printing_diff = is_diff_requested
        self.path_output = path_output.resolve() if path_output else None

    def execute(self) -> None:
        original_content = self.path_note.read_text()
        formatted_content = format_single(self.path_note)

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
