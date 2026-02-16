from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

from bim.params.show_note import ShowNoteParams

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


class CommandShowNote:
    def __init__(
        self,
        params: ShowNoteParams,
        repo: ZettelRepository,
        formatter: ZettelFormatter,
    ) -> None:
        self.params = params
        self.repo = repo
        self.formatter = formatter

    def execute(self) -> CommandResult:
        results: list[str] = []
        warnings: list[str] = []
        use_case = PrintZettelUseCase(self.formatter)

        for path in self.params.paths:
            if not path.is_file():
                warnings.append(f"{path} doesn't exist")
                continue

            zettel = self.repo.find_by_location(str(path))
            results.append(use_case.execute(zettel.get_data()))

        if not results:
            return CommandResult(success=False, error="\n".join(warnings), warnings=warnings)

        return CommandResult(
            success=True,
            output="\n---\n".join(results),
            warnings=warnings,
            metadata={"count": len(results)},
        )
