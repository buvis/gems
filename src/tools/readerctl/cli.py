from pathlib import Path

import click
from buvis.pybase.adapters import console


@click.group(help="CLI tool to manage Reader from Readwise")
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj["token"] = None


@cli.command("login")
@click.pass_context
def login(ctx: click.Context) -> None:
    from readerctl.commands.login.login import CommandLogin

    cmd = CommandLogin()
    token = cmd.execute()
    ctx.obj["token"] = token


@cli.command("add")
@click.option("-u", "--url", default="NONE", help="URL to add to Reader")
@click.option("-f", "--file", default="NONE", help="File with URLs to add to Reader")
@click.pass_context
def add(ctx: click.Context, url: str, file: str) -> None:
    from readerctl.commands.add.add import CommandAdd
    from readerctl.commands.login.login import CommandLogin

    if url != "NONE" or file != "NONE":
        cmd_login = CommandLogin()
        token = cmd_login.execute()
        ctx.obj["token"] = token

    token = ctx.obj.get("token")
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
