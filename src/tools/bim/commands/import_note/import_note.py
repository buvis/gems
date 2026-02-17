from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel import ReadZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

from bim.params.import_note import ImportNoteParams

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


class CommandImportNote:
    def __init__(
        self,
        params: ImportNoteParams,
        path_zettelkasten: Path,
        repo: ZettelRepository,
        formatter: ZettelFormatter,
    ) -> None:
        if not path_zettelkasten.is_dir():
            raise FileNotFoundError(f"Zettelkasten directory not found: {path_zettelkasten}")
        self.params = params
        self.path_zettelkasten = path_zettelkasten
        self.repo = repo
        self.formatter = formatter

    def execute(self) -> CommandResult:
        messages: list[str] = []
        warnings: list[str] = []
        imported_count = 0

        for path in self.params.paths:
            if not path.is_file():
                warnings.append(f"{path} doesn't exist")
                continue

            reader = ReadZettelUseCase(self.repo)
            note = reader.execute(str(path))

            if note.type == "project":
                note.data.metadata["resources"] = f"[project resources]({path.parent.resolve().as_uri()})"

            if self.params.tags is not None:
                note.tags = self.params.tags

            if note.id is None:
                warnings.append(f"Note at {path} has no ID, skipping")
                continue

            path_output = self.path_zettelkasten / f"{note.id}.md"
            if path_output.is_file() and not self.params.force:
                warnings.append(f"{path_output} already exists")
                continue

            formatted = PrintZettelUseCase(self.formatter).execute(note.get_data())
            path_output.write_text(formatted, encoding="utf-8")
            messages.append(f"Imported {path.name} as {path_output.name}")
            imported_count += 1

            if self.params.remove_original:
                path.unlink()
                messages.append(f"Removed {path}")

        if not messages and warnings:
            return CommandResult(success=False, error="\n".join(warnings), warnings=warnings)

        return CommandResult(
            success=True,
            output="\n".join(messages),
            warnings=warnings,
            metadata={"imported_count": imported_count},
        )
