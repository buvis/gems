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


def _report_steps(steps: Iterable[StepResult]) -> bool:
    """Render every step (success and failure) and report whether any failed.

    All steps are rendered before the caller acts on the return, so the user
    sees every failure — the CLI must not stop at the first one. Returns ``True``
    when at least one step failed, so the CLI layer can exit nonzero (a cron job
    treating an incomplete backup as success is the bug this closes).
    """
    any_failed = False
    for step in steps:
        _report_step(step)
        if not step.success:
            any_failed = True
    return any_failed


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


def _show_excludes(cfg: BackupConfig, instance_name: str, for_path: str) -> bool:
    """Print the resolved exclude set for ``instance_name`` under ``--for`` path.

    Renders the global exclude set (already post-``excludes+`` / ``excludes-``)
    and, when ``for_path`` is given, the ``.bkpignore`` add / ``!``-unignore
    rules effective under that path — resolved with the same layering the
    archive walk uses. Writes no archive. Without ``--for`` prints the global
    set only and notes that path-dependent ``.bkpignore`` rules are omitted.

    Returns ``True`` on a terminal validation failure (unknown instance, or an
    instance with no source) so the CLI layer can exit nonzero — a typo like
    ``backup --show-excludes typo`` must not look like a successful inspection
    to a script.
    """
    from pathlib import Path

    from backup.shared.bkpignore import ExcludeState, resolve_state_for_path

    instance = cfg.instances.get(instance_name)
    if instance is None:
        console.failure(f"unknown instance '{instance_name}'")
        return True

    console.info(f"resolved global excludes for '{instance_name}':")
    for pattern in sorted(cfg.excludes):
        console.info(f"  {pattern}")

    if not for_path:
        console.info("(.bkpignore rules omitted — path-dependent; pass --for <path> to resolve them)")
        return False

    source_raw = instance.with_.get("source")
    if not isinstance(source_raw, str) or not source_raw:
        console.failure(f"instance '{instance_name}' has no source configured")
        return True

    source = Path(source_raw).expanduser()
    target = Path(for_path).expanduser()
    base_state = ExcludeState(base_excludes=frozenset(cfg.excludes))
    state = resolve_state_for_path(source, base_state, target)

    console.info(f".bkpignore rules effective under {target}:")
    if state.applied:
        for rule in state.applied:
            console.info(f"  {rule}")
    else:
        console.info("  none")
    return False


def _select_plan(
    cfg: BackupConfig,
    plan: list[tuple[str, BackupInstance]],
    only: tuple[str, ...],
    tags: tuple[str, ...],
) -> tuple[list[tuple[str, BackupInstance]], bool]:
    """Narrow ``plan`` by ``--only`` names and ``--tag`` tags, reporting skips via console.

    Returns the narrowed plan plus a flag that is ``True`` when any requested
    ``--only`` name was unknown to the config. Valid names still run (the caller
    executes whatever survived), but the flag lets the CLI exit nonzero so a typo
    that leaves an empty or reduced plan cannot make a scheduled backup silently
    do nothing (or less) while reporting success.
    """
    had_unknown = False
    only_names = _parse_only(only)
    if only_names:
        selected_names = {name for name, _ in plan}
        for requested in sorted(only_names):
            if requested not in cfg.instances:
                console.failure(f"unknown instance '{requested}', skipping")
                had_unknown = True
            elif requested not in selected_names:
                console.info(f"'{requested}' is disabled, skipping")
        plan = [(name, instance) for name, instance in plan if name in only_names]

    if tags:
        wanted = set(tags)
        plan = [(name, instance) for name, instance in plan if wanted & set(instance.tags)]

    return plan, had_unknown


def _run_plan(cfg: BackupConfig, plan: list[tuple[str, BackupInstance]], *, dry_run: bool) -> bool:
    """Run the selected plan, rendering every step; return whether any failed.

    Rendering all steps before returning means the user sees every failure (the
    CLI must not stop at the first). Returns ``True`` if any step failed so the
    caller can exit nonzero — a cron job treating an incomplete backup as success
    is the bug this closes. A ``FatalError`` from the runner is surfaced via
    ``console.panic`` (which exits).
    """
    from backup.runner import Runner

    try:
        return _report_steps(Runner(cfg, dry_run=dry_run).run(plan))
    except FatalError as exc:
        console.panic(str(exc))
        return True  # unreachable: panic exits, but keeps the type honest


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

    # --for only qualifies --show-excludes' read-only inspection; supplied alone
    # it used to be silently ignored while a real backup RAN. Reject it up front.
    if for_path and not show_excludes:
        console.failure("--for requires --show-excludes")
        raise SystemExit(1)

    # NOTE (deferred, finding 4114829192): backup's load_config() searches the
    # default config locations independently of buvis_options' --config/--config-dir,
    # so `backup --config FILE` resolves BackupSettings from FILE yet still runs the
    # default backup plan. Honoring --config/--config-dir here would need the resolved
    # path forwarded via ctx.obj by the SHARED buvis_options wrapper in src/lib/, which
    # affects every tool — out of scope for this PR, tracked as its own PRD. Do NOT
    # wire it in by touching src/lib/.
    try:
        cfg = load_config()
    except FatalError as exc:
        console.panic(str(exc))
        return

    if show_excludes:
        failed = _show_excludes(cfg, show_excludes, for_path)
        if failed:
            raise SystemExit(1)
        return

    plan = applicable_instances(cfg)
    plan, unknown_only = _select_plan(cfg, plan, only, tags)

    if list_plan:
        if not plan:
            console.info("no configured instances")
        else:
            for name, instance in plan:
                console.info(_describe(name, instance))
        if unknown_only:
            raise SystemExit(1)
        return

    if source or out:
        if len(plan) != 1:
            console.failure(
                f"--source/--out require exactly one selected instance (via --only); {len(plan)} selected",
            )
            raise SystemExit(1)
        name, instance = plan[0]
        plan = [(name, _apply_overrides(instance, source, out))]

    any_failed = _run_plan(cfg, plan, dry_run=dry_run)
    # An unknown --only name (typo) must also fail the run, so a scheduled
    # backup can't silently do nothing (or less) after a mistyped selector.
    if any_failed or unknown_only:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
