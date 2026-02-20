from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandNormalize:
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def execute(self) -> CommandResult:
        # TODO: implement
        return CommandResult(success=True, output="Normalize command not yet implemented")
