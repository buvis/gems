from __future__ import annotations

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings

from hello_world.settings import HelloWorldSettings


@click.group(help="CLI tool as script proof of concept", invoke_without_command=True)
@buvis_options(settings_class=HelloWorldSettings)
@click.option(
    "-f",
    "--font",
    default=None,
    help="Font to use for stylized printing.",
)
@click.option(
    "-l",
    "--list-fonts",
    is_flag=True,
    show_default=True,
    default=False,
    help="List available fonts",
)
@click.option(
    "-r",
    "--random-font",
    is_flag=True,
    show_default=True,
    default=False,
    help="Pick random font",
)
@click.option(
    "--diag",
    is_flag=True,
    default=False,
    help="Print python runtime and dependency info",
)
@click.argument("text", default=None, required=False)
@click.pass_context
def cli(
    ctx: click.Context,
    text: str | None,
    font: str | None,
    *,
    list_fonts: bool = False,
    random_font: bool = False,
    diag: bool = False,
) -> None:
    settings = get_settings(ctx, HelloWorldSettings)

    if diag:
        from hello_world.commands.diagnostics.diagnostics import CommandDiagnostics

        result = CommandDiagnostics().execute()
        if result.output:
            console.print(result.output, mode="raw")
        return

    try:
        import pyfiglet  # noqa: F401
    except ImportError:
        console.panic(
            "hello-world requires the 'hello-world' extra. Install with: uv tool install buvis-gems[hello-world]"
        )
        return

    if list_fonts:
        from hello_world.commands.list_fonts.list_fonts import CommandListFonts

        result = CommandListFonts().execute()
        if result.output:
            console.print(result.output, mode="raw")
        return

    import pyfiglet as _pyfiglet

    resolved_font = font if font is not None else settings.font
    if random_font:
        import random

        all_fonts: list[str] = _pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
        resolved_font = random.choice(all_fonts)  # noqa: S311
        console.print(f"Random font selected: {resolved_font}", mode="raw")

    available_fonts: list[str] = _pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
    if resolved_font not in available_fonts:
        resolved_font = settings.font

    resolved_text = text if text is not None else settings.text

    from hello_world.commands.print_figlet.print_figlet import CommandPrintFiglet

    result = CommandPrintFiglet(font=resolved_font, text=resolved_text).execute()
    console.nl()
    if result.output:
        console.print(result.output, mode="raw")


if __name__ == "__main__":
    cli()
