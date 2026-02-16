from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.update_zettel_use_case import UpdateZettelUseCase

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


class CommandEditNote:
    def __init__(
        self,
        paths: list[Path],
        repo: ZettelRepository,
        changes: dict[str, Any] | None = None,
        target: str = "metadata",
    ) -> None:
        self.paths = paths
        self.repo = repo
        self.changes = changes
        self.target = target

    def execute(self) -> CommandResult:
        if self.changes is None:
            return CommandResult(success=False, error="No changes provided")

        results: list[str] = []
        warnings: list[str] = []
        use_case = UpdateZettelUseCase(self.repo)

        for path in self.paths:
            if not path.is_file():
                warnings.append(f"{path} doesn't exist")
                continue
            zettel = self.repo.find_by_location(str(path))
            use_case.execute(zettel, self.changes, self.target)
            results.append(f"Updated {path.name}")

        if not results:
            error = "\n".join(warnings) if warnings else "No notes updated"
            return CommandResult(success=False, error=error, warnings=warnings)

        return CommandResult(
            success=True,
            output="\n".join(results),
            warnings=warnings,
            metadata={"updated_count": len(results)},
        )
