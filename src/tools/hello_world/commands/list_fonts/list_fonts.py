from __future__ import annotations

from buvis.pybase.adapters import console


class CommandListFonts:
    def execute(self: CommandListFonts) -> None:
        import pyfiglet

        fonts: list[str] = pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
        console.print("\n".join(sorted(fonts)), mode="raw")
