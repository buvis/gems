from __future__ import annotations

from typing import TYPE_CHECKING

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError

from backup.settings import BackupSettings

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backup.config import BackupConfig, BackupInstance
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


def _apply_overrides(instance: BackupInstance, source: str, out: str) -> BackupInstance:
    """Return a copy of ``instance`` with ``source`` / ``out`` overridden in ``with_``.

    A non-empty flag value replaces the instance's configured value for a
    one-shot run; an empty value leaves the config value untouched (flag wins
    over config). The frozen model is copied rather than mutated.
    """
    merged = dict(instance.with_)
    if source:
        merged["source"] = source
    if out:
        merged["out"] = out
    return instance.model_copy(update={"with_": merged})


def _show_excludes(cfg: BackupConfig, instance_name: str, for_path: str) -> None:
    """Print the resolved exclude set for ``instance_name`` under ``--for`` path.

    Renders the global exclude set (already post-``excludes+`` / ``excludes-``)
    and, when ``for_path`` is given, the ``.bkpignore`` add / ``!``-unignore
    rules effective under that path — resolved with the same layering the
    archive walk uses. Writes no archive. Without ``--for`` prints the global
    set only and notes that path-dependent ``.bkpignore`` rules are omitted.
    """
    from pathlib import Path

    from backup.shared.bkpignore import ExcludeState, resolve_state_for_path

    instance = cfg.instances.get(instance_name)
    if instance is None:
        console.failure(f"unknown instance '{instance_name}'")
        return

    console.info(f"resolved global excludes for '{instance_name}':")
    for pattern in sorted(cfg.excludes):
        console.info(f"  {pattern}")

    if not for_path:
        console.info("(.bkpignore rules omitted — path-dependent; pass --for <path> to resolve them)")
        return

    source_raw = instance.with_.get("source")
    if not isinstance(source_raw, str) or not source_raw:
        console.failure(f"instance '{instance_name}' has no source configured")
        return

    source = Path(source_raw).expanduser()
    target = Path(for_path).expanduser()
    base_state = ExcludeState(excludes=frozenset(cfg.excludes))
    state = resolve_state_for_path(source, base_state, target)

    console.info(f".bkpignore rules effective under {target}:")
    if state.applied:
        for rule in state.applied:
            console.info(f"  {rule}")
    else:
        console.info("  none")


def _select_plan(
    cfg: BackupConfig,
    plan: list[tuple[str, BackupInstance]],
    only: tuple[str, ...],
    tags: tuple[str, ...],
) -> list[tuple[str, BackupInstance]]:
    """Narrow ``plan`` by ``--only`` names and ``--tag`` tags, reporting skips via console."""
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

    return plan


@click.command(help="Run configured backup archives")
@click.option("--only", multiple=True, help="Run only these instance names (comma-separated or repeated).")
@click.option("--tag", "tags", multiple=True, help="Run only instances carrying one of these tags.")
@click.option("--list", "list_plan", is_flag=True, help="Print the configured instances and exit.")
@click.option("--dry-run", is_flag=True, help="Walk and report what would be archived without writing it.")
@click.option("--source", default="", help="Override the single selected instance's source for this run.")
@click.option("--out", default="", help="Override the single selected instance's out path for this run.")
@click.option(
    "--show-excludes",
    "show_excludes",
    default="",
    help="Print an instance's resolved exclude set and exit (read-only).",
)
@click.option("--for", "for_path", default="", help="Resolve .bkpignore rules under this path for --show-excludes.")
@buvis_options(settings_class=BackupSettings)
@click.pass_context
def cli(  # noqa: PLR0917  # Click binds one callback arg per CLI option
    ctx: click.Context,  # noqa: ARG001
    only: tuple[str, ...],
    tags: tuple[str, ...],
    list_plan: bool,
    dry_run: bool,
    source: str,
    out: str,
    show_excludes: str,
    for_path: str,
) -> None:
    from backup.config import applicable_instances, load_config
    from backup.runner import Runner

    try:
        cfg = load_config()
    except FatalError as exc:
        console.panic(str(exc))
        return

    if show_excludes:
        _show_excludes(cfg, show_excludes, for_path)
        return

    plan = applicable_instances(cfg)
    plan = _select_plan(cfg, plan, only, tags)

    if list_plan:
        if not plan:
            console.info("no configured instances")
            return
        for name, instance in plan:
            console.info(_describe(name, instance))
        return

    if source or out:
        if len(plan) != 1:
            console.failure(
                f"--source/--out require exactly one selected instance (via --only); {len(plan)} selected",
            )
            return
        name, instance = plan[0]
        plan = [(name, _apply_overrides(instance, source, out))]

    try:
        _report_steps(Runner(cfg, dry_run=dry_run).run(plan))
    except FatalError as exc:
        console.panic(str(exc))


if __name__ == "__main__":
    cli()
