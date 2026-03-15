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
        console.require_import("readerctl")
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


def _ensure_token(token_file: Path) -> str | None:
    """Login and return token, or None on failure."""
    from readerctl.commands.login.login import CommandLogin

    cmd_login = CommandLogin(token_file=token_file)

    try:
        login_result = cmd_login.execute()
    except FatalError as e:
        console.panic(str(e))
        return None

    if login_result.success:
        console.success(login_result.output or "Done")
        return login_result.metadata.get("token")

    console.failure(login_result.error or "Failed")
    return None


def _add_urls(token: str, urls: list[str]) -> None:
    """Add one or more URLs via CommandAdd."""
    from readerctl.commands.add.add import CommandAdd

    cmd = CommandAdd(token=token)
    for u in urls:
        result = cmd.execute(u.strip())
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
        from readerctl.commands.add.add import CommandAdd  # noqa: F401
    except ImportError:
        console.require_import("readerctl")
        return

    if url is None and file is None:
        console.panic("Provide --url or --file")
        return

    settings = get_settings(ctx, ReaderctlSettings)
    token = _ensure_token(Path(settings.token_file).expanduser())
    if not token:
        console.panic("Not logged in. Run 'readerctl login' first.")
        return

    if url is not None:
        _add_urls(token, [url])
    elif file is not None:
        path = Path(file)
        if not path.is_file():
            console.panic(f"File {file} not found")
            return
        _add_urls(token, path.read_text().splitlines())


if __name__ == "__main__":
    cli()
