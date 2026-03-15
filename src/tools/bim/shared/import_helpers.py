from __future__ import annotations

from pathlib import Path
from typing import Any

from buvis.pybase.adapters import console
from buvis.pybase.configuration import GlobalSettings


def resolve_output_path(
    note: Any,
    path_output: Path,
    path_note: Path,
    path_zettelkasten: Path,
) -> Path:
    overwrite_confirmed = False

    while path_output.is_file() and not overwrite_confirmed:
        console.failure(f"{path_output} already exists")
        console.nl()
        console.print(path_output.read_text(encoding="utf-8"), mode="raw")
        console.nl()
        overwrite_file = console.confirm("Overwrite file?")

        if overwrite_file:
            overwrite_confirmed = True
        else:
            alternative_note_id = (note.id or 0) + 1
            alternative_path_output = path_zettelkasten / f"{alternative_note_id}.md"

            while alternative_path_output.is_file():
                alternative_note_id += 1
                alternative_path_output = path_zettelkasten / f"{alternative_note_id}.md"

            accept_alternative_id = console.confirm(
                f"Change ID to {alternative_note_id}?",
            )

            if accept_alternative_id:
                path_output = alternative_path_output
                note.data.metadata["id"] = alternative_note_id
            else:
                console.panic(f"Can't import {path_note}")
                return path_output

    return path_output


def interactive_import(path_note: Path, path_zettelkasten: Path, global_settings: GlobalSettings) -> None:
    if not path_note.is_file():
        console.failure(f"{path_note} doesn't exist")
        return

    from buvis.pybase.zettel import ReadZettelUseCase
    from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

    from bim.dependencies import get_formatter, get_repo

    original_content = path_note.read_text(encoding="utf-8")
    repo = get_repo()
    reader = ReadZettelUseCase(repo)
    note = reader.execute(str(path_note))

    if note.type == "project":
        note.data.metadata["resources"] = f"[project resources]({path_note.parent.resolve().as_uri()})"

    if note.id is None:
        console.failure(f"Note at {path_note} has no ID, skipping")
        return

    path_output = path_zettelkasten / f"{note.id}.md"
    formatted_content = PrintZettelUseCase(get_formatter()).execute(note.get_data())
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

    path_output = resolve_output_path(note, path_output, path_note, path_zettelkasten)

    if not note.tags and global_settings.ollama_model:
        from buvis.pybase.formatting import StringOperator

        console.nl()
        console.warning("There are no tags in this note. Suggesting via ollama...")
        console.nl()
        new_tags = []
        suggested = StringOperator.suggest_tags(
            markdown_content,
            global_settings.ollama_model,
            global_settings.ollama_url,
        )
        for suggested_tag in suggested:
            add_tag = console.confirm(f"Tag with '{suggested_tag}'?")
            if add_tag:
                new_tags.append(suggested_tag)
        note.tags = new_tags
        formatted_content = PrintZettelUseCase(get_formatter()).execute(note.get_data())

    path_output.write_text(formatted_content, encoding="utf-8")
    console.success(f"Note imported as {path_output}")
    remove_file = console.confirm("Do you want to remove the original?")

    if remove_file:
        path_note.unlink()
        console.success(f"{path_note} was removed")
