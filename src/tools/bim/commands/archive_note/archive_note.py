from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.delete_zettel_use_case import DeleteZettelUseCase
from buvis.pybase.zettel.application.use_cases.update_zettel_use_case import UpdateZettelUseCase

from bim.params.archive_note import ArchiveNoteParams

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


class CommandArchiveNote:
    def __init__(
        self,
        params: ArchiveNoteParams,
        path_archive: Path,
        path_zettelkasten: Path,
        repo: ZettelRepository,
    ) -> None:
        self.params = params
        self.path_archive = path_archive
        self.path_zettelkasten = path_zettelkasten
        self.repo = repo

    def execute(self) -> CommandResult:
        messages: list[str] = []
        update_use_case = UpdateZettelUseCase(self.repo)
        delete_use_case = DeleteZettelUseCase(self.repo)
        archive = not self.params.undo
        destination = self.path_archive if archive else self.path_zettelkasten

        for path in self.params.paths:
            zettel = self.repo.find_by_location(str(path))
            data = zettel.get_data()

            changes: dict[str, object] = {"processed": archive}
            if data.metadata.get("type") == "project":
                changes["completed"] = archive

            if archive:
                destination.mkdir(parents=True, exist_ok=True)
            dest = destination / path.name
            source = data.file_path
            data.file_path = str(dest)

            update_use_case.execute(zettel, changes)
            data.file_path = source
            delete_use_case.execute(zettel)

            action = "Archived" if archive else "Unarchived"
            messages.append(f"{action} {path.name}")

        return CommandResult(
            success=True,
            output="\n".join(messages),
            metadata={"count": len(messages)},
        )
