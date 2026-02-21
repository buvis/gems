from __future__ import annotations

import sys

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError

from sysup.commands.step_result import StepResult
from sysup.settings import SysupSettings


def _report_steps(steps: list[StepResult]) -> None:
    for step in steps:
        if step.success:
            console.success(step.message or f"{step.label} updated")
        else:
            console.failure(step.message or f"{step.label} failed")


@click.group(help="System update tools")
@buvis_options(settings_class=SysupSettings)
@click.pass_context
def cli(ctx: click.Context) -> None:
    pass


@cli.command("mac", help="Run macOS system and tooling updates")
def mac() -> None:
    if sys.platform != "darwin":
        console.panic("mac command is only available on macOS")

    from sysup.commands.mac.mac import CommandMac

    try:
        steps = CommandMac().execute()
    except FatalError as e:
        console.panic(str(e))
        return

    _report_steps(steps)


@cli.command("pip", help="Upgrade pip and outdated Python packages")
def pip() -> None:
    from sysup.commands.pip.pip import CommandPip

    _report_steps(CommandPip().execute())


@cli.command("wsl", help="Run WSL/Linux package updates")
def wsl() -> None:
    if sys.platform != "linux":
        console.panic("wsl command is only available on Linux")

    from sysup.commands.wsl.wsl import CommandWsl

    try:
        steps = CommandWsl().execute()
    except FatalError as e:
        console.panic(str(e))
        return

    _report_steps(steps)


if __name__ == "__main__":
    cli()
