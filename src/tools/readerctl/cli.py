from __future__ import annotations

from pathlib import Path

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options, get_settings
from buvis.pybase.result import FatalError

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

    try:
        result = cmd.execute()
    except FatalError as e:
        console.panic(str(e))
        return

    if result.success:
        console.success(result.output or "Done")
    else:
        console.failure(result.error or "Failed")


@cli.command("add")
@click.option("-u", "--url", default=None, help="URL to add to Reader")
@click.option("-f", "--file", default=None, help="File with URLs to add to Reader")
@click.pass_context
def add(ctx: click.Context, url: str | None, file: str | None) -> None:
    try:
        from readerctl.commands.add.add import CommandAdd
        from readerctl.commands.login.login import CommandLogin
    except ImportError:
        console.panic("readerctl requires the 'readerctl' extra. Install with: uv tool install buvis-gems[readerctl]")
        return

    settings = get_settings(ctx, ReaderctlSettings)
    token_file = Path(settings.token_file).expanduser()
    token = None

    if url is not None or file is not None:
        cmd_login = CommandLogin(token_file=token_file)

        try:
            login_result = cmd_login.execute()
        except FatalError as e:
            console.panic(str(e))
            return

        if login_result.success:
            console.success(login_result.output or "Done")
            token = login_result.metadata.get("token")
        else:
            console.failure(login_result.error or "Failed")

    if not token:
        console.panic("Not logged in. Run 'readerctl login' first.")
        return

    if url is not None:
        cmd = CommandAdd(token=token)
        result = cmd.execute(url)
        if result.success:
            console.success(result.output or "Done")
        else:
            console.failure(result.error or "Failed")
    elif file is not None:
        if Path(file).is_file():
            cmd = CommandAdd(token=token)
            with Path(file).open() as f:
                urls = f.readlines()

            for u in urls:
                result = cmd.execute(u.strip())
                if result.success:
                    console.success(result.output or "Done")
                else:
                    console.failure(result.error or "Failed")
        else:
            console.panic(f"File {file} not found")


if __name__ == "__main__":
    cli()
