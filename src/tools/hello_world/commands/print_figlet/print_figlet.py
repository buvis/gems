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
        try:
            from pyfiglet import Figlet

            f = Figlet(font=self.font)
        except ImportError:
            f = None

        if f is None:
            output = f"Hello {self.text}!\n\n"
        else:
            output = f.renderText(f"Hello {self.text}!")

        return CommandResult(success=True, output=output)
