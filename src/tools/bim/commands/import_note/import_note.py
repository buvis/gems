from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel import (
    MarkdownZettelFormatter,
    MarkdownZettelRepository,
    ReadZettelUseCase,
)
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel


class CommandImportNote:
    def __init__(
        self: "CommandImportNote",
        path_note: Path,
        path_zettelkasten: Path,
    ) -> None:
        if not path_note.is_file():
            raise FileNotFoundError(f"Note not found: {path_note}")
        self.path_note = path_note

        if not path_zettelkasten.is_dir():
            raise FileNotFoundError(f"Zettelkasten directory not found: {path_zettelkasten}")
        self.path_zettelkasten = path_zettelkasten

    def _resolve_output_path(self: "CommandImportNote", note: Zettel, path_output: Path) -> Path:
        overwrite_confirmed = False

        while path_output.is_file() and not overwrite_confirmed:
            console.failure(f"{path_output} already exists")
            console.nl()
            console.print(path_output.read_text(), mode="raw")
            console.nl()
            overwrite_file = console.confirm("Overwrite file?")

            if overwrite_file:
                overwrite_confirmed = True
            else:
                assert note.id is not None
                alternative_note_id = note.id + 1
                alternative_path_output = self.path_zettelkasten / f"{alternative_note_id}.md"

                while alternative_path_output.is_file():
                    alternative_note_id = note.id + 1
                    alternative_path_output = self.path_zettelkasten / f"{alternative_note_id}.md"

                accept_alternative_id = console.confirm(
                    f"Change ID to {alternative_note_id}?",
                )

                if accept_alternative_id:
                    path_output = alternative_path_output
                else:
                    console.panic(f"Can't import {self.path_note}")

        return path_output

    def execute(self: "CommandImportNote") -> None:
        original_content = self.path_note.read_text()
        repo = MarkdownZettelRepository()
        reader = ReadZettelUseCase(repo)
        formatter = MarkdownZettelFormatter()
        note = reader.execute(str(self.path_note))

        if note.type == "project":
            note.data.metadata["resources"] = (
                f"[project resources]({self.path_note.parent.resolve().as_uri()})"
            )

        path_output = self.path_zettelkasten / f"{note.id}.md"
        formatted_content = formatter.format(note.get_data())
        _, _, markdown_content = formatted_content.partition("\n---\n")

        console.print_side_by_side(
            "Original",
            original_content,
            "Formatted",
            formatted_content,
            mode_left="raw",
            mode_right="raw",
        )
        console.nl()

        is_import_approved = console.confirm(
            "Check the resulting note and compare to original. Should I continue importing?"
        )

        if not is_import_approved:
            console.warning("Import cancelled by user")
            return

        path_output = self._resolve_output_path(note, path_output)

        if not note.tags:
            console.nl()
            console.warning("There are no tags in this note. I will suggest some.")
            console.nl()
            new_tags = []
            for suggested_tag in StringOperator.suggest_tags(markdown_content):
                add_tag = console.confirm(f"Tag with '{suggested_tag}'?")
                if add_tag:
                    new_tags.append(suggested_tag)
            note.tags = new_tags
            formatted_content = formatter.format(note.get_data())

        path_output.write_bytes(formatted_content.encode("utf-8"))
        console.success(f"Note imported as {path_output}")
        remove_file = console.confirm("Do you want to remove the original?")

        if remove_file:
            self.path_note.unlink()
            console.success(f"{self.path_note} was removed")
