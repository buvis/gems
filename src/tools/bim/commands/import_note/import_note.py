from __future__ import annotations

from pathlib import Path

from buvis.pybase.adapters import console
from buvis.pybase.formatting import StringOperator
from buvis.pybase.zettel import ReadZettelUseCase
from buvis.pybase.zettel.infrastructure.formatting.markdown_zettel_formatter.markdown_zettel_formatter import (
    MarkdownZettelFormatter,
)
from buvis.pybase.zettel.domain.entities.zettel.zettel import Zettel
from bim.dependencies import get_repo


def import_single(
    path_note: Path,
    path_zettelkasten: Path,
    *,
    tags: list[str] | None = None,
    force_overwrite: bool = False,
    remove_original: bool = False,
    quiet: bool = False,
) -> str | None:
    """Import a note to zettelkasten. Non-interactive."""
    repo = get_repo()
    reader = ReadZettelUseCase(repo)
    formatter = MarkdownZettelFormatter()
    note = reader.execute(str(path_note))

    if note.type == "project":
        note.data.metadata["resources"] = (
            f"[project resources]({path_note.parent.resolve().as_uri()})"
        )

    if tags is not None:
        note.tags = tags

    if note.id is None:
        console.failure(f"Note at {path_note} has no ID, skipping")
        return None

    path_output = path_zettelkasten / f"{note.id}.md"

    if path_output.is_file() and not force_overwrite:
        raise FileExistsError(f"{path_output} already exists")

    formatted = formatter.format(note.get_data())
    path_output.write_text(formatted, encoding="utf-8")
    msg = f"Imported {path_note.name} as {path_output.name}"
    if not quiet:
        console.success(msg)

    if remove_original:
        path_note.unlink()
        rm_msg = f"Removed {path_note}"
        if not quiet:
            console.success(rm_msg)

    return msg


class CommandImportNote:
    def __init__(
        self,
        paths: list[Path],
        path_zettelkasten: Path,
        *,
        tags: list[str] | None = None,
        force: bool = False,
        remove_original: bool = False,
        scripted: bool = False,
    ) -> None:
        if not path_zettelkasten.is_dir():
            raise FileNotFoundError(f"Zettelkasten directory not found: {path_zettelkasten}")
        self.paths = paths
        self.path_zettelkasten = path_zettelkasten
        self.tags = tags
        self.force = force
        self.remove_original = remove_original
        self.scripted = scripted

    def _resolve_output_path(self, note: Zettel, path_output: Path, path_note: Path) -> Path:
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
                alternative_note_id = note.id + 1
                alternative_path_output = self.path_zettelkasten / f"{alternative_note_id}.md"

                while alternative_path_output.is_file():
                    alternative_note_id += 1
                    alternative_path_output = self.path_zettelkasten / f"{alternative_note_id}.md"

                accept_alternative_id = console.confirm(
                    f"Change ID to {alternative_note_id}?",
                )

                if accept_alternative_id:
                    path_output = alternative_path_output
                    note.data.metadata["id"] = alternative_note_id
                else:
                    console.panic(f"Can't import {path_note}")

        return path_output

    def _interactive(self) -> None:
        path_note = self.paths[0]
        if not path_note.is_file():
            console.failure(f"{path_note} doesn't exist")
            return
        original_content = path_note.read_text()
        repo = get_repo()
        reader = ReadZettelUseCase(repo)
        formatter = MarkdownZettelFormatter()
        note = reader.execute(str(path_note))

        if note.type == "project":
            note.data.metadata["resources"] = (
                f"[project resources]({path_note.parent.resolve().as_uri()})"
            )

        if note.id is None:
            console.failure(f"Note at {path_note} has no ID, skipping")
            return

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

        path_output = self._resolve_output_path(note, path_output, path_note)

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
            path_note.unlink()
            console.success(f"{path_note} was removed")

    def execute(self) -> None:
        if self.scripted:
            for path in self.paths:
                if not path.is_file():
                    console.failure(f"{path} doesn't exist")
                    continue
                import_single(
                    path,
                    self.path_zettelkasten,
                    tags=self.tags,
                    force_overwrite=self.force,
                    remove_original=self.remove_original,
                )
        else:
            self._interactive()
