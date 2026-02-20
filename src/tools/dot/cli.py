from __future__ import annotations

import click
from buvis.pybase.adapters import ShellAdapter, console
from buvis.pybase.configuration import buvis_options, get_settings

from dot.settings import DotSettings


@click.group(help="CLI for bare repo dotfiles")
@buvis_options(settings_class=DotSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("status", help="Report status")
def status() -> None:
    from dot.commands.status.status import CommandStatus

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandStatus(shell=shell)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        details = result.metadata.get("details")
        console.failure(result.error or "Failed", details=details)


@cli.command("add", help="Add changes")
@click.argument("file_path", required=False)
@click.pass_context
def add(ctx: click.Context, file_path: str | None = None) -> None:
    settings = get_settings(ctx, DotSettings)

    # CLI overrides settings
    resolved_path = file_path if file_path is not None else settings.add_file_path

    from dot.commands.add.add import CommandAdd

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandAdd(shell=shell, file_path=resolved_path)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


@cli.command("pull", help="Pull dotfiles and update submodules")
def pull() -> None:
    from dot.commands.pull.pull import CommandPull

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandPull(shell=shell)
    result = cmd.execute()

    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


@cli.command("commit", help="Commit dotfiles changes")
@click.option("-m", "--message", required=True, help="Commit message")
def commit(message: str) -> None:
    from dot.commands.commit.commit import CommandCommit

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandCommit(shell=shell, message=message)
    result = cmd.execute()

    for w in result.warnings:
        console.warning(w)
    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


@cli.command("push", help="Push dotfiles to remote")
def push() -> None:
    from dot.commands.push.push import CommandPush

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandPush(shell=shell)
    result = cmd.execute()

    if result.success:
        if result.output:
            console.success(result.output)
    else:
        console.failure(result.error or "Failed")


if __name__ == "__main__":
    cli()
