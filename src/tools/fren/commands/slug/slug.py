from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult


class CommandSlug:
    def __init__(self, paths: tuple[str, ...]) -> None:
        self.paths = [Path(p) for p in paths]

    def execute(self) -> CommandResult:
        # TODO: implement
        return CommandResult(success=True, output="Slug command not yet implemented")
