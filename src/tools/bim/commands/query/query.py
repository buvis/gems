from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel.application.use_cases.query_zettels_use_case import QueryZettelsUseCase

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository

BUNDLED_QUERY_DIR = Path(__file__).parent


class CommandQuery:
    def __init__(
        self,
        spec: Any,
        repo: ZettelRepository,
        evaluator: Any,
        default_directory: str,
    ) -> None:
        self.spec = spec
        self.repo = repo
        self.evaluator = evaluator
        self.default_directory = default_directory

    def execute(self) -> CommandResult:
        spec = self.spec
        if spec.source.directory is None:
            spec.source.directory = self.default_directory

        directory = str(Path(spec.source.directory).expanduser().resolve())
        use_case = QueryZettelsUseCase(self.repo, self.evaluator)
        rows = use_case.execute(spec)
        columns = list(rows[0].keys()) if rows else []

        return CommandResult(
            success=True,
            metadata={
                "rows": rows,
                "columns": columns,
                "count": len(rows),
                "directory": directory,
                "spec": spec,
            },
        )
