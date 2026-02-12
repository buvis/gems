from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.zettel import (
    MarkdownZettelFormatter,
    MarkdownZettelRepository,
    ReadZettelUseCase,
)


class CommandFormatNote:
    def __init__(
        self: "CommandFormatNote",
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

    def execute(self: "CommandFormatNote") -> None:
        original_content = self.path_note.read_text()
        repo = MarkdownZettelRepository()
        reader = ReadZettelUseCase(repo)
        formatter = MarkdownZettelFormatter()
        note = reader.execute(str(self.path_note))
        formatted_content = formatter.format(note.get_data())

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
