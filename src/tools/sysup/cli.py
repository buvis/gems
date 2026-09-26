from __future__ import annotations

from typing import TYPE_CHECKING

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError

from sysup.settings import SysupSettings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sysup.config import SysupCommand
    from sysup.step_result import StepResult


def _report_step(step: StepResult) -> None:
    if step.success:
        console.success(step.message or f"{step.label} updated")
    else:
        console.failure(step.message or f"{step.label} failed")


def _report_steps(steps: Iterable[StepResult]) -> None:
    for step in steps:
        _report_step(step)


def _parse_only(only: tuple[str, ...]) -> set[str]:
    names: set[str] = set()
    for item in only:
        names.update(part.strip() for part in item.split(",") if part.strip())
    return names


def _describe(name: str, command: SysupCommand) -> str:
    kind = f"use:{command.use}" if command.use is not None else "run"
    guards = []
    if command.when.os is not None:
        guards.append(f"os={command.when.os}")
    if command.when.check is not None:
        guards.append(f"check={command.when.check}")
    suffix = f" ({', '.join(guards)})" if guards else ""
    return f"{command.order:>4}  {name}  [{kind}]{suffix}"


@click.command(help="Run applicable system and tooling updates")
@click.option("--only", multiple=True, help="Run only these command names (comma-separated or repeated).")
@click.option("--tag", "tags", multiple=True, help="Run only commands carrying one of these tags.")
@click.option("--list", "list_plan", is_flag=True, help="Print the resolved plan for this host and exit.")
@click.option("--dry-run", is_flag=True, help="Show what would run without running it.")
@buvis_options(settings_class=SysupSettings)
@click.pass_context
def cli(
    ctx: click.Context,  # noqa: ARG001
    only: tuple[str, ...],
    tags: tuple[str, ...],
    list_plan: bool,
    dry_run: bool,
) -> None:
    from sysup.config import applicable_commands, load_config
    from sysup.runner import Runner

    try:
        cfg = load_config()
    except FatalError as exc:
        console.panic(str(exc))
        return

    plan = applicable_commands(cfg)

    only_names = _parse_only(only)
    if only_names:
        selected_names = {name for name, _ in plan}
        for requested in sorted(only_names):
            if requested not in cfg.commands:
                console.failure(f"unknown command '{requested}', skipping")
            elif requested not in selected_names:
                console.info(f"'{requested}' does not apply on this host, skipping")
        plan = [(name, command) for name, command in plan if name in only_names]

    if tags:
        wanted = set(tags)
        plan = [(name, command) for name, command in plan if wanted & set(command.tags)]

    if list_plan:
        if not plan:
            console.info("no applicable commands for this host")
            return
        for name, command in plan:
            console.info(_describe(name, command))
        return

    try:
        _report_steps(Runner(cfg, dry_run=dry_run).run(plan))
    except FatalError as exc:
        console.panic(str(exc))


if __name__ == "__main__":
    cli()
