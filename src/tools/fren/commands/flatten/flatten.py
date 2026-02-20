from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandFlatten:
    def __init__(self, source: str, destination: str) -> None:
        self.source = Path(source)
        self.destination = Path(destination)

    def execute(self) -> CommandResult:
        # TODO: implement
        return CommandResult(success=True, output="Flatten command not yet implemented")
