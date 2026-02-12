from buvis.pybase.adapters import console


class CommandPrintFiglet:
    def __init__(self: "CommandPrintFiglet", font: str, text: str) -> None:
        self.font = font
        self.text = text

    def execute(self: "CommandPrintFiglet") -> None:
        try:
            from pyfiglet import Figlet

            f = Figlet(font=self.font)
        except ImportError:
            f = None

        console.nl()

        if f is None:
            console.print(f"Hello {self.text}!\n\n", mode="raw")
        else:
            console.print(f.renderText(f"Hello {self.text}!"), mode="raw")
