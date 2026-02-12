from __future__ import annotations

import click
from buvis.pybase.configuration import buvis_options, get_settings

from hello_world.commands import CommandDiagnostics, CommandListFonts, CommandPrintFiglet
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
        CommandDiagnostics().execute()
        return

    try:
        import pyfiglet  # noqa: F401
    except ImportError as _exc:
        raise ImportError(
            "hello-world requires the 'hello-world' extra. Install with: uv tool install buvis-gems[hello-world]"
        ) from _exc

    if list_fonts:
        CommandListFonts().execute()
        return

    CommandPrintFiglet(
        font=font,
        text=text,
        settings=settings,
        random_font=random_font,
    ).execute()


if __name__ == "__main__":
    cli()
