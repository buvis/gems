from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.configuration import get_settings

from bim.settings import BimSettings

__all__ = ["register_serve_command"]


def register_serve_command(cli: click.Group) -> None:
    cli.add_command(serve)


@click.command("serve", help="Start web dashboard")
@click.option("-p", "--port", default=8000, type=int)
@click.option("-H", "--host", default="127.0.0.1")
@click.option("--no-browser", is_flag=True, default=False)
@click.pass_context
def serve(
    ctx: click.Context,
    port: int,
    host: str,
    *,
    no_browser: bool,
) -> None:
    from bim.commands.serve.serve import CommandServe
    from bim.params.serve import ServeParams

    settings = get_settings(ctx, BimSettings)
    params = ServeParams(
        default_directory=str(Path(settings.path_zettelkasten).expanduser().resolve()),
        archive_directory=str(Path(settings.path_archive).expanduser().resolve()),
        host=host,
        port=port,
        no_browser=no_browser,
    )
    cmd = CommandServe(params=params)
    cmd.execute()
