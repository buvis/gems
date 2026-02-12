import re
import sys
from importlib.metadata import distributions, requires
from pathlib import Path

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
        console.print(f"Script: {Path(__file__).resolve()}", mode="raw")
        console.print(f"Python: {sys.executable}", mode="raw")
        console.print("\nDirect dependencies:", mode="raw")
        reqs = requires("hello-world") or []
        direct_deps = {re.split(r"[<>=!~\[;]", r)[0].lower().replace("-", "_") for r in reqs}
        for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
            name = dist.metadata["Name"]
            normalized = name.lower().replace("-", "_")
            if normalized in direct_deps:
                version = dist.version
                location = getattr(dist, "_path", None)
                location = location.parent if location else "unknown"
                console.print(f"  {name}=={version} ({location})", mode="raw")
        return

    try:
        import pyfiglet
    except ImportError as _exc:
        raise ImportError(
            "hello-world requires the 'hello-world' extra. Install with: uv tool install buvis-gems[hello-world]"
        ) from _exc

    from hello_world.commands.print_figlet.print_figlet import CommandPrintFiglet

    if list_fonts:
        fonts: list[str] = pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
        console.print("\n".join(sorted(fonts)), mode="raw")
        return

    # Resolve font: CLI > settings
    resolved_font = font if font is not None else settings.font
    if random_font:
        import random

        all_fonts: list[str] = pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
        resolved_font = random.choice(all_fonts)  # noqa: S311
        console.print(f"Random font selected: {resolved_font}", mode="raw")

    available_fonts: list[str] = pyfiglet.FigletFont.getFonts()  # type: ignore[no-untyped-call]
    if resolved_font not in available_fonts:
        resolved_font = settings.font

    # Resolve text: CLI > settings
    resolved_text = text if text is not None else settings.text

    cmd = CommandPrintFiglet(font=resolved_font, text=resolved_text)
    cmd.execute()


if __name__ == "__main__":
    cli()
