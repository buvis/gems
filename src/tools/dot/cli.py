from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from buvis.pybase.adapters import ShellAdapter, console
from buvis.pybase.configuration import buvis_options, get_settings

from dot.settings import DotSettings


def _dotfiles_root() -> str:
    return os.environ.get("DOTFILES_ROOT", str(Path.home()))


def _launch_tui(theme: str = "textual-dark", *, confirm_revert: bool = True) -> None:
    try:
        from dot.tui.app import DotApp
    except ImportError:
        click.echo("dot TUI requires the 'dot' extra: pip install buvis-gems[dot]")
        raise SystemExit(1)

    DotApp(dotfiles_root=_dotfiles_root(), theme=theme, confirm_revert=confirm_revert).run()


@click.group(invoke_without_command=True, help="CLI for bare repo dotfiles")
@buvis_options(settings_class=DotSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        settings = get_settings(ctx, DotSettings)
        _launch_tui(theme=settings.theme, confirm_revert=settings.confirm_revert)


@cli.command("tui", help="Launch dotfiles TUI")
@click.pass_context
def tui(ctx: click.Context) -> None:
    settings = get_settings(ctx, DotSettings)
    _launch_tui(theme=settings.theme, confirm_revert=settings.confirm_revert)


@cli.command("status", help="Report status")
def status() -> None:
    from dot.commands.status.status import CommandStatus

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandStatus(shell=shell, dotfiles_root=_dotfiles_root())
    result = cmd.execute()
    console.report_result(
        result,
        on_failure=lambda r: console.failure(r.error or "Failed", details=r.metadata.get("details")),
    )


@cli.command("materialize", help="Link host-specific config listed in host-links")
@click.option("--hook", is_flag=True, help="Run from a git hook: skip hook install and git calls")
def materialize(hook: bool) -> None:
    from dot.commands.materialize.materialize import CommandMaterialize

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(
        CommandMaterialize(shell=shell, dotfiles_root=_dotfiles_root(), install_hooks=not hook).execute()
    )


@cli.command("setup", help="Clone dotfiles onto a fresh host and link host config")
@click.argument("url", required=False)
@click.pass_context
def setup(ctx: click.Context, url: str | None = None) -> None:
    settings = get_settings(ctx, DotSettings)
    remote_url = url or settings.remote_url
    if not remote_url:
        console.panic("remote URL required: dot setup <url> or set BUVIS_DOT_REMOTE_URL")
        return

    from dot.commands.setup.setup import CommandSetup

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandSetup(shell=shell, dotfiles_root=_dotfiles_root(), remote_url=remote_url).execute())


@cli.command("add", help="Add changes")
@click.argument("file_path", required=False)
@click.pass_context
def add(ctx: click.Context, file_path: str | None = None) -> None:
    settings = get_settings(ctx, DotSettings)

    # CLI overrides settings
    resolved_path = file_path if file_path is not None else settings.add_file_path

    from dot.commands.add.add import CommandAdd

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandAdd(shell=shell, dotfiles_root=_dotfiles_root(), file_path=resolved_path)
    console.report_result(cmd.execute())


@cli.command("encrypt", help="Register a file for git-secret encryption")
@click.argument("file_path")
def encrypt(file_path: str) -> None:
    from dot.commands.encrypt.encrypt import CommandEncrypt

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandEncrypt(shell=shell, dotfiles_root=_dotfiles_root(), file_path=file_path).execute())


@cli.command("rm", help="Remove file from tracking (keeps file on disk)")
@click.argument("file_path")
def rm(file_path: str) -> None:
    from dot.commands.rm.rm import CommandRm

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandRm(shell=shell, dotfiles_root=_dotfiles_root(), file_path=file_path).execute())


@cli.command("delete", help="Delete file from tracking and disk")
@click.argument("file_path")
def delete(file_path: str) -> None:
    from dot.commands.delete.delete import CommandDelete

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandDelete(shell=shell, dotfiles_root=_dotfiles_root(), file_path=file_path).execute())


@cli.command("pull", help="Pull dotfiles and update submodules")
def pull() -> None:
    import sys

    from dot.commands.pull.pull import CommandPull
    from dot.hostlinks.rescue import Resolution

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandPull(shell=shell, dotfiles_root=_dotfiles_root())

    # Plan rescue
    plan = cmd.plan()

    if plan.error:
        console.failure(plan.error)
        return

    # Handle collisions
    resolutions: dict[str, Resolution] = {}
    if plan.collisions:
        if sys.stdin.isatty():
            for entry in plan.collisions:
                console.warning(f"{entry.target} and {entry.source} both exist and differ")
                choice = console.choose(
                    "Resolve",
                    ["keep-source", "keep-target", "cancel"],
                    default="cancel",
                )
                resolutions[entry.target] = Resolution(choice)
        # Non-TTY: no prompts, execute will report unresolved collisions

    # Passphrase prompt
    passphrase = None
    if shell.is_command_available("git-secret"):
        console.info("GPG passphrase required to decrypt secret files")

    result = cmd.execute(plan=plan, resolutions=resolutions, passphrase=passphrase)
    console.report_result(result)


@cli.command("commit", help="Commit dotfiles changes")
@click.argument("message")
def commit(message: str) -> None:
    from dot.commands.commit.commit import CommandCommit

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandCommit(shell=shell, dotfiles_root=_dotfiles_root(), message=message).execute())


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
    console.report_result(CommandUnstage(shell=shell, dotfiles_root=_dotfiles_root(), file_path=file_path).execute())


@cli.command("push", help="Push dotfiles to remote")
def push() -> None:
    from dot.commands.push.push import CommandPush

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(CommandPush(shell=shell, dotfiles_root=_dotfiles_root()).execute())


@cli.command("localize", help="Make a file or directory host-specific")
@click.argument("path")
@click.option("--to", "source", help="Source path (default: .local/<path>)")
@click.option("--shared", is_flag=True, help="Register a host-value filter instead of moving the file")
def localize(path: str, source: str | None = None, *, shared: bool = False) -> None:
    if shared and source is not None:
        console.panic("--shared cannot be combined with --to")
        return

    shell = ShellAdapter(suppress_logging=True)

    if shared:
        from dot.commands.localize.share import CommandShare

        console.report_result(
            CommandShare(
                shell=shell,
                dotfiles_root=_dotfiles_root(),
                path=path,
            ).execute()
        )
        return

    from dot.commands.localize.localize import CommandLocalize

    console.report_result(
        CommandLocalize(
            shell=shell,
            dotfiles_root=_dotfiles_root(),
            path=path,
            source=source,
        ).execute()
    )


def _filter_home() -> str:
    from dot.hostfilter import resolve_home

    return resolve_home(os.environ.get("GIT_WORK_TREE"), os.getcwd())


@cli.group("filter", hidden=True, help="Git clean/smudge filter plumbing (internal)")
def filter_group() -> None:
    """Group the byte-stream filters git invokes; not a user-facing command."""


# Discovery R12: the filter streams carry git's blob payload, not console output, so
# both handlers write raw bytes - the one sanctioned exception to dot's console-only rule.
@filter_group.command("clean", help="Replace the host home path with the @HOME@ token")
@click.argument("path")
def filter_clean(path: str) -> None:
    from dot.hostfilter import TOKEN, clean

    data = sys.stdin.buffer.read()
    home = _filter_home()

    try:
        cleaned = clean(data, home)
    except ValueError:
        # path comes from argv, so it can carry surrogate-escaped non-UTF-8 bytes.
        sys.stderr.buffer.write(
            b"dot filter: " + os.fsencode(path) + b" already contains " + TOKEN + b"; the token is reserved\n"
        )
        raise SystemExit(1) from None

    sys.stdout.buffer.write(cleaned)


@filter_group.command("smudge", help="Replace the @HOME@ token with the host home path")
@click.argument("path", expose_value=False)
def filter_smudge() -> None:
    from dot.hostfilter import smudge

    sys.stdout.buffer.write(smudge(sys.stdin.buffer.read(), _filter_home()))


if __name__ == "__main__":
    cli()
