from __future__ import annotations

from buvis.pybase.result import CommandResult


class CommandCreateTimeblock:
    def __init__(self, duration: int) -> None:
        self.duration = duration

    def execute(self) -> CommandResult:
        return CommandResult(
            success=True,
            output=f"Would create a timeblock of {self.duration} minutes",
        )
