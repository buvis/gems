from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from braid.domain.engine import BraidError, Mode, resolve_settings, run

if TYPE_CHECKING:
    from braid.domain.engine import ComposeRequest


class CommandCompose:
    def __init__(self, request: ComposeRequest) -> None:
        self.request = request

    def execute(self) -> CommandResult:
        lines: list[str] = []
        try:
            settings = resolve_settings(self.request)
            result = run(settings, lines.append)
        except (BraidError, OSError) as error:
            return CommandResult(
                success=False,
                output="\n".join(lines),
                error=f"braid: {error}",
                metadata={"drift": 0, "unmanaged": 0, "exit_code": 2},
            )
        change_label = "drift" if settings.mode is Mode.CHECK else "change(s)"
        lines.append(
            "braid: "
            f"{result.linked} linked, {result.generated} generated, {result.current} current, "
            f"{result.ignored} ignored, {result.removed} removed, {result.backed_up} backed up, "
            f"{result.configured} configured, {result.unmanaged} unmanaged, "
            f"{result.drift} {change_label}"
        )
        exit_code = 1 if settings.mode is Mode.CHECK and result.drift else 0
        return CommandResult(
            success=exit_code == 0,
            output="\n".join(lines),
            error=None,
            metadata={"drift": result.drift, "unmanaged": result.unmanaged, "exit_code": exit_code},
        )
