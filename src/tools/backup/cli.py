from __future__ import annotations

from typing import TYPE_CHECKING

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError

from backup.settings import BackupSettings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backup.config import BackupInstance
    from backup.step_result import StepResult


def _report_step(step: StepResult) -> None:
    if step.success:
        console.success(step.message or f"{step.label} archived")
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


def _describe(name: str, instance: BackupInstance) -> str:
    tags = f" [tags: {', '.join(instance.tags)}]" if instance.tags else ""
    return f"{instance.order:>4}  {name}  (use:{instance.use}){tags}"


@click.command(help="Run configured backup archives")
@click.option("--only", multiple=True, help="Run only these instance names (comma-separated or repeated).")
@click.option("--tag", "tags", multiple=True, help="Run only instances carrying one of these tags.")
@click.option("--list", "list_plan", is_flag=True, help="Print the configured instances and exit.")
@click.option("--dry-run", is_flag=True, help="Walk and report what would be archived without writing it.")
@buvis_options(settings_class=BackupSettings)
@click.pass_context
def cli(
    ctx: click.Context,  # noqa: ARG001
    only: tuple[str, ...],
    tags: tuple[str, ...],
    list_plan: bool,
    dry_run: bool,
) -> None:
    from backup.config import applicable_instances, load_config
    from backup.runner import Runner

    try:
        cfg = load_config()
    except FatalError as exc:
        console.panic(str(exc))
        return

    plan = applicable_instances(cfg)

    only_names = _parse_only(only)
    if only_names:
        selected_names = {name for name, _ in plan}
        for requested in sorted(only_names):
            if requested not in cfg.instances:
                console.failure(f"unknown instance '{requested}', skipping")
            elif requested not in selected_names:
                console.info(f"'{requested}' is disabled, skipping")
        plan = [(name, instance) for name, instance in plan if name in only_names]

    if tags:
        wanted = set(tags)
        plan = [(name, instance) for name, instance in plan if wanted & set(instance.tags)]

    if list_plan:
        if not plan:
            console.info("no configured instances")
            return
        for name, instance in plan:
            console.info(_describe(name, instance))
        return

    try:
        _report_steps(Runner(cfg, dry_run=dry_run).run(plan))
    except FatalError as exc:
        console.panic(str(exc))


if __name__ == "__main__":
    cli()
