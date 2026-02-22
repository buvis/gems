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
    console.report_result(
        result,
        on_failure=lambda r: console.failure(r.error or "Failed", details=r.metadata.get("details")),
    )


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
    console.report_result(cmd.execute())


@cli.command("pull", help="Pull dotfiles and update submodules")
def pull() -> None:
    from dot.commands.pull.pull import CommandPull

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandPull(shell=shell).execute())


@cli.command("commit", help="Commit dotfiles changes")
@click.option("-m", "--message", required=True, help="Commit message")
def commit(message: str) -> None:
    from dot.commands.commit.commit import CommandCommit

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandCommit(shell=shell, message=message).execute())


@cli.command("push", help="Push dotfiles to remote")
def push() -> None:
    from dot.commands.push.push import CommandPush

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandPush(shell=shell).execute())


if __name__ == "__main__":
    cli()
