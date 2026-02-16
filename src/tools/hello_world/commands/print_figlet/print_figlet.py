from __future__ import annotations

from buvis.pybase.adapters import console
from hello_world.settings import HelloWorldSettings


class CommandPrintFiglet:
    def __init__(
        self,
        font: str | None = None,
        text: str | None = None,
        *,
        settings: HelloWorldSettings | None = None,
        random_font: bool = False,
    ) -> None:
        if settings is None:
            self.font = font or ""
            self.text = text or ""
            return

        import pyfiglet

        resolved_font = font if font is not None else settings.font
        if random_font:
            import random

            all_fonts: list[str] = pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
            resolved_font = random.choice(all_fonts)  # noqa: S311
            console.print(f"Random font selected: {resolved_font}", mode="raw")

        available_fonts: list[str] = pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
        if resolved_font not in available_fonts:
            resolved_font = settings.font

        self.font = resolved_font
        self.text = text if text is not None else settings.text

    def execute(self) -> None:
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
