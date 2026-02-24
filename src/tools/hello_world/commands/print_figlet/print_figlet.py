from __future__ import annotations

from buvis.pybase.result import CommandResult


class CommandPrintFiglet:
    def __init__(
        self,
        font: str = "",
        text: str = "",
    ) -> None:
        self.font = font
        self.text = text

    def execute(self) -> CommandResult:
        output: str
        try:
            from pyfiglet import Figlet

            f = Figlet(font=self.font)
            output = str(f.renderText(f"Hello {self.text}!"))
        except ImportError:
            output = f"Hello {self.text}!\n\n"

        return CommandResult(success=True, output=output)
