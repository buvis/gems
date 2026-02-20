from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandDirectorize:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def execute(self) -> CommandResult:
        # TODO: implement
        return CommandResult(success=True, output="Directorize command not yet implemented")
