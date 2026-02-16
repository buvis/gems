from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult
from buvis.pybase.zettel import ReadZettelUseCase
from buvis.pybase.zettel.application.use_cases.print_zettel_use_case import PrintZettelUseCase

if TYPE_CHECKING:
    from buvis.pybase.zettel.domain.interfaces.zettel_formatter import ZettelFormatter
    from buvis.pybase.zettel.domain.interfaces.zettel_repository import ZettelRepository


class CommandFormatNote:
    def __init__(
        self,
        paths: list[Path],
        repo: ZettelRepository,
        formatter: ZettelFormatter,
        path_output: Path | None = None,
    ) -> None:
        self.paths = paths
        self.repo = repo
        self.formatter = formatter
        self.path_output = path_output.resolve() if path_output else None

    def execute(self) -> CommandResult:
        warnings: list[str] = []
        reader = ReadZettelUseCase(self.repo)
        printer = PrintZettelUseCase(self.formatter)

        if len(self.paths) > 1:
            formatted_count = 0
            for path in self.paths:
                if not path.is_file():
                    warnings.append(f"{path} doesn't exist")
                    continue
                zettel = reader.execute(str(path))
                formatted_content = printer.execute(zettel.get_data())
                path.write_text(formatted_content, encoding="utf-8")
                formatted_count += 1
            return CommandResult(
                success=True,
                metadata={"formatted_count": formatted_count},
                warnings=warnings,
            )

        path = self.paths[0]
        if not path.is_file():
            return CommandResult(success=False, error=f"{path} doesn't exist")

        original_content = path.read_text(encoding="utf-8")
        zettel = reader.execute(str(path))
        formatted_content = printer.execute(zettel.get_data())

        if self.path_output:
            try:
                self.path_output.write_text(formatted_content, encoding="utf-8")
            except OSError as exc:
                return CommandResult(
                    success=False,
                    error=f"An error occurred while writing to the file: {exc}",
                )
            except UnicodeEncodeError:
                return CommandResult(
                    success=False,
                    error="The text could not be encoded with UTF-8",
                )
            return CommandResult(success=True, metadata={"written_to": str(self.path_output)})

        return CommandResult(
            success=True,
            output=formatted_content,
            metadata={"original": original_content},
        )
