from __future__ import annotations

from buvis.pybase.result import CommandResult


class CommandListFonts:
    def execute(self) -> CommandResult:
        import pyfiglet

        fonts: list[str] = pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
        return CommandResult(success=True, output="\n".join(sorted(fonts)))
