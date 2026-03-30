from __future__ import annotations

import os
from pathlib import Path

import click
from buvis.pybase.adapters import ShellAdapter, console
from buvis.pybase.configuration import buvis_options, get_settings

from dot.settings import DotSettings


def _launch_tui() -> None:
    try:
        from dot.tui.app import DotApp
    except ImportError:
        click.echo("dot TUI requires the 'dot' extra: pip install buvis-gems[dot]")
        raise SystemExit(1)

    dotfiles_root = os.environ.get("DOTFILES_ROOT", str(Path.home()))
    DotApp(dotfiles_root=dotfiles_root).run()


@click.group(invoke_without_command=True, help="CLI for bare repo dotfiles")
@buvis_options(settings_class=DotSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        _launch_tui()


@cli.command("tui", help="Launch dotfiles TUI")
def tui() -> None:
    _launch_tui()


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


@cli.command("encrypt", help="Register a file for git-secret encryption")
@click.argument("file_path")
def encrypt(file_path: str) -> None:
    from dot.commands.encrypt.encrypt import CommandEncrypt

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandEncrypt(shell=shell, file_path=file_path).execute())


@cli.command("rm", help="Remove file from dotfiles tracking")
@click.argument("file_path")
def rm(file_path: str) -> None:
    from dot.commands.rm.rm import CommandRm

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandRm(shell=shell, file_path=file_path).execute())


@cli.command("pull", help="Pull dotfiles and update submodules")
def pull() -> None:
    from dot.commands.pull.pull import CommandPull

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandPull(shell=shell).execute())


@cli.command("commit", help="Commit dotfiles changes")
@click.argument("message")
def commit(message: str) -> None:
    from dot.commands.commit.commit import CommandCommit

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandCommit(shell=shell, message=message).execute())


@cli.command(
    "run",
    help="Run arbitrary git command on dotfiles repo",
    context_settings={"ignore_unknown_options": True},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def run(args: tuple[str, ...]) -> None:
    from dot.commands.run.run import CommandRun

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandRun(shell=shell, args=args).execute())


@cli.command("unstage", help="Unstage files, keep local changes")
@click.argument("file_path", required=False)
def unstage(file_path: str | None = None) -> None:
    from dot.commands.unstage.unstage import CommandUnstage

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandUnstage(shell=shell, file_path=file_path).execute())


@cli.command("push", help="Push dotfiles to remote")
def push() -> None:
    from dot.commands.push.push import CommandPush

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandPush(shell=shell).execute())


if __name__ == "__main__":
    cli()
