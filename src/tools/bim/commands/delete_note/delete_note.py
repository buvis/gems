from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.delete_zettel_use_case import DeleteZettelUseCase

from bim.params.delete_note import DeleteNoteParams

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


class CommandDeleteNote:
    def __init__(self, params: DeleteNoteParams, repo: ZettelRepository) -> None:
        self.params = params
        self.repo = repo

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        deleted_count = 0
        use_case = DeleteZettelUseCase(self.repo)

        for path in self.params.paths:
            if not path.is_file():
                warnings.append(f"{path} doesn't exist")
                continue
            zettel = self.repo.find_by_location(str(path))
            use_case.execute(zettel)
            deleted_count += 1

        if deleted_count == 0 and warnings:
            return CommandResult(success=False, error="\n".join(warnings), warnings=warnings)

        return CommandResult(
            success=True,
            metadata={"deleted_count": deleted_count},
            warnings=warnings,
        )
