from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings

from readerctl.settings import ReaderctlSettings


@click.group(help="CLI tool to manage Reader from Readwise")
@buvis_options(settings_class=ReaderctlSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)


@cli.command("login")
@click.pass_context
def login(ctx: click.Context) -> None:
    try:
        from readerctl.commands.login.login import CommandLogin
    except ImportError:
        console.panic("readerctl requires the 'readerctl' extra. Install with: uv tool install buvis-gems[readerctl]")
        return

    settings = get_settings(ctx, ReaderctlSettings)
    token_file = Path(settings.token_file).expanduser()
    cmd = CommandLogin(token_file=token_file)
    cmd.execute()


@cli.command("add")
@click.option("-u", "--url", default="NONE", help="URL to add to Reader")
@click.option("-f", "--file", default="NONE", help="File with URLs to add to Reader")
@click.pass_context
def add(ctx: click.Context, url: str, file: str) -> None:
    try:
        from readerctl.commands.add.add import CommandAdd
        from readerctl.commands.login.login import CommandLogin
    except ImportError:
        console.panic("readerctl requires the 'readerctl' extra. Install with: uv tool install buvis-gems[readerctl]")
        return

    settings = get_settings(ctx, ReaderctlSettings)
    token_file = Path(settings.token_file).expanduser()
    token = None

    if url != "NONE" or file != "NONE":
        cmd_login = CommandLogin(token_file=token_file)
        token = cmd_login.execute()

    if not token:
        console.panic("Not logged in. Run 'readerctl login' first.")
        return

    if url != "NONE":
        cmd = CommandAdd(token=token)
        cmd.execute(url)
    elif file != "NONE":
        if Path(file).is_file():
            cmd = CommandAdd(token=token)
            with Path(file).open() as f:
                urls = f.readlines()

            for u in urls:
                cmd.execute(u.strip())
        else:
            console.panic(f"File {file} not found")


if __name__ == "__main__":
    cli()
