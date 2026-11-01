from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError
from rich.text import Text

from backup.settings import BackupSettings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from rich.status import Status

    from backup.config import BackupConfig, BackupInstance
    from backup.step_result import ProgressEvent, StepResult


def _format_progress(event: ProgressEvent, elapsed: float) -> str:
    percentage = ""
    if (
        event.done_bytes is not None
        and event.total_bytes is not None
        and event.total_bytes > 0
        and event.phase != "finalizing"
    ):
        percentage = f" [{min(99, event.done_bytes * 100 // event.total_bytes)}%]"
    minutes, seconds = divmod(max(0, int(elapsed)), 60)
    return f"{event.label} {event.phase}{percentage} {minutes}:{seconds:02d}"


class _LiveProgress:
    def __init__(self) -> None:
        self._events: dict[str, ProgressEvent] = {}
        self._started: dict[str, float] = {}
        self._status: Status | None = None
        self._running = False

    def on_progress(self, event: ProgressEvent) -> None:
        if event.label not in self._started:
            self._started[event.label] = time.monotonic()
        self._events[event.label] = event
        self.refresh()

    def refresh(self) -> None:
        if not self._events:
            self.close()
            return
        if self._status is None:
            self._status = console.status("")
        if not self._running:
            self._running = True
            self._status.start()
        now = time.monotonic()
        message = " | ".join(
            _format_progress(event, now - self._started[label]) for label, event in self._events.items()
        )
        self._status.update(Text(message))

    def finish(self, label: str) -> None:
        self._events.pop(label, None)
        self._started.pop(label, None)
        self.refresh()

    def close(self) -> None:
        if self._status is not None and self._running:
            self._status.stop()
            self._running = False


def _report_step(step: StepResult) -> None:
    if step.skipped:
        console.warning(step.message or f"{step.label} skipped")
    elif step.success:
        console.success(step.message or f"{step.label} archived")
    else:
        message = f"{step.label} cancelled" if step.message == "cancelled" else step.message
        console.failure(message or f"{step.label} failed")


def _report_steps(
    steps: Iterable[StepResult],
    *,
    dry_run: bool = False,
    on_interrupt: Callable[[], None] | None = None,
    on_result: Callable[[StepResult], None] | None = None,
) -> bool:
    """Render every outcome, retrying interrupted output while draining workers.

    Return whether any step failed so the caller exits nonzero and cron sees a
    failed backup.
    """
    archived = skipped = failed = 0
    iterator = iter(steps)
    pending = None
    while True:
        try:
            if pending is None:
                pending = next(iterator)
            if on_result is not None:
                on_result(pending)
            _report_step(pending)
            if not pending.success:
                failed += 1
            elif pending.skipped:
                skipped += 1
            else:
                archived += 1
            pending = None
        except StopIteration:
            break
        except KeyboardInterrupt:
            if on_interrupt is None:
                raise
            on_interrupt()
    verb = "previewed" if dry_run else "archived"
    while True:
        try:
            console.info(f"{verb} {archived}, skipped {skipped}, failed {failed}")
            break
        except KeyboardInterrupt:
            if on_interrupt is None:
                raise
            on_interrupt()
    return failed > 0


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


def _override_selected(
    plan: list[tuple[str, BackupInstance]], source: str, out: str
) -> list[tuple[str, BackupInstance]]:
    if not (source or out):
        return plan
    if len(plan) != 1:
        console.failure(
            f"--source/--out require exactly one selected instance (via --only); {len(plan)} selected",
        )
        raise SystemExit(1)
    name, instance = plan[0]
    return [(name, _apply_overrides(instance, source, out))]


def _list_instances(plan: list[tuple[str, BackupInstance]]) -> None:
    if not plan:
        console.info("no configured instances")
    else:
        for name, instance in plan:
            console.info(_describe(name, instance))


def _load_config(ctx: click.Context) -> BackupConfig | None:
    from backup.config import load_config

    # Honour the same --config / --config-dir the buvis_options wrapper resolved
    # settings from, so the backup PLAN and BackupSettings come from ONE source.
    # The wrapper publishes the raw selection on ctx.obj (None when unset); pass
    # it through so `backup --config FILE` runs the plan from FILE and
    # `--config-dir DIR` discovers it under DIR. (PRD 00084 closed the split that
    # was deferred from PR #179.)
    obj = ctx.obj or {}
    config_dir = obj.get("config_dir")
    config_path = obj.get("config_path")
    try:
        return load_config(config_dir=config_dir, config_path=config_path)
    except FatalError as exc:
        console.panic(str(exc))
        return None


def _show_excludes(cfg: BackupConfig, instance_name: str, for_path: str) -> bool:
    """Print the resolved exclude set for ``instance_name`` under ``--for`` path.

    Renders the instance exclude set (after inheritance, removals and additions)
    and, when ``for_path`` is given, the ``.bkpignore`` add / ``!``-unignore
    rules effective under that path — resolved with the same layering the
    archive walk uses. Writes no archive. Without ``--for`` prints the instance
    set only and notes that path-dependent ``.bkpignore`` rules are omitted.

    Returns ``True`` on a terminal validation failure (unknown instance, or an
    instance with no source) so the CLI layer can exit nonzero — a typo like
    ``backup --show-excludes typo`` must not look like a successful inspection
    to a script.
    """
    from pathlib import Path

    from backup.config import effective_excludes
    from backup.shared.bkpignore import ExcludeState, resolve_state_for_path

    instance = cfg.instances.get(instance_name)
    if instance is None:
        console.failure(f"unknown instance '{instance_name}'")
        return True

    excludes = effective_excludes(cfg, instance)
    console.info(f"resolved excludes for '{instance_name}':")
    for pattern in excludes:
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
    base_state = ExcludeState(base_excludes=frozenset(excludes))
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


def _run_plan(
    cfg: BackupConfig,
    plan: list[tuple[str, BackupInstance]],
    *,
    dry_run: bool,
    plan_only: bool,
    jobs: int = 3,
    quiet: bool = False,
) -> bool:
    """Render plan/results with eligible live status; return whether either failed."""

    from backup.runner import Runner

    live = _LiveProgress() if not quiet and sys.stdout.isatty() and not dry_run and not plan_only else None
    on_progress, on_tick = (live.on_progress, live.refresh) if live else (None, None)
    on_result = (lambda step: live.finish(step.label)) if live else None
    try:
        runner = Runner(cfg, dry_run=dry_run, jobs=jobs, on_progress=on_progress, on_tick=on_tick)
        if plan_only:
            entries = runner.plan(plan)
            for entry in entries:
                message = f"{entry.label}  {entry.status}  {entry.source} -> {entry.out}"
                if entry.reason:
                    message += f"  ({entry.reason})"
                if entry.replaces:
                    message += "  [replaces existing]"
                console.info(message)
            return any(entry.status == "fail" for entry in entries)
        steps = runner.run(plan)
        try:
            failed = _report_steps(steps, dry_run=dry_run, on_interrupt=runner.request_cancel, on_result=on_result)
        finally:
            steps.close()
        if runner.interrupted:
            while True:
                try:
                    names = ", ".join(runner.cancelled_names) or "no unfinished instances"
                    console.failure("interrupted: " + names)
                    break
                except KeyboardInterrupt:
                    runner.request_cancel()
            raise SystemExit(130)
        return failed
    except FatalError as exc:
        console.panic(str(exc))
        return True  # unreachable: panic exits, but keeps the type honest
    finally:
        if live is not None:
            live.close()


@click.command(help="Run configured backup archives")
@click.option("--only", multiple=True, help="Run only these instance names (comma-separated or repeated).")
@click.option("--tag", "tags", multiple=True, help="Run only instances carrying one of these tags.")
@click.option("--list", "list_plan", is_flag=True, help="Print the configured instances and exit.")
@click.option("--plan", "plan_only", is_flag=True, help="Print the selected archive plan without walking sources.")
@click.option("--dry-run", is_flag=True, help="Walk and report what would be archived without writing it.")
@click.option("--quiet", is_flag=True, help="Hide live progress; keep final results and the summary.")
@click.option("--jobs", type=int, default=3, show_default=True, help="Run at most this many archive instances at once.")
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
    ctx: click.Context,
    only: tuple[str, ...],
    tags: tuple[str, ...],
    list_plan: bool,
    plan_only: bool,
    dry_run: bool,
    quiet: bool,
    jobs: int,
    source: str,
    out: str,
    show_excludes: str,
    for_path: str,
) -> None:
    from backup.config import applicable_instances

    if jobs < 1:
        console.failure("--jobs must be at least 1")
        raise SystemExit(1)
    if plan_only and dry_run:
        console.failure("--plan and --dry-run are mutually exclusive")
        raise SystemExit(1)
    # --for only qualifies --show-excludes; reject it before a real backup runs.
    if for_path and not show_excludes:
        console.failure("--for requires --show-excludes")
        raise SystemExit(1)

    cfg = _load_config(ctx)
    if cfg is None:
        return
    if show_excludes:
        failed = _show_excludes(cfg, show_excludes, for_path)
        if failed:
            raise SystemExit(1)
        return

    plan = applicable_instances(cfg)
    plan, unknown_only = _select_plan(cfg, plan, only, tags)

    if list_plan:
        _list_instances(plan)
        if unknown_only:
            raise SystemExit(1)
        return
    plan = _override_selected(plan, source, out)
    any_failed = _run_plan(cfg, plan, dry_run=dry_run, plan_only=plan_only, jobs=jobs, quiet=quiet)
    # Unknown --only names must fail rather than silently omit backup work.
    if any_failed or unknown_only:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
