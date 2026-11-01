# Devon 4 adversarial proof

Backend: OpenAI gpt-6.1-sol/high (logical opus).

Allowed selector, run once per experiment with timeout=300 seconds:

`uv run pytest tests/tools/backup/test_progress.py -k "cli or quiet or format" -q --tb=line`

Eight wrong implementations passed independently. One initial scaffolding attempt failed because the original result renderer omitted the label for a real archive message; the test caught that omission. The scaffolding was corrected before the eight isolated exploit runs.

Original cli.py SHA-256: e6256f685456cf4e6c18dbad16b28e6c9887b8b78c563a684169afcd39ee86e1

Every experiment restored cli.py to the exact original bytes in a finally block. CHANGELOG.md and test files were not edited. No commits or state edits.

## Temporary shared scaffolding

The checked-in cli.py lacked the new public helpers and options. This temporary implementation supplies those interfaces. Each passing exploit below is independently applied to this scaffolding, then original source is restored.

```python
from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

from rich.text import Text
from backup.step_result import ProgressEvent

import click
from buvis.pybase.adapters import console
from buvis.pybase.configuration import buvis_options
from buvis.pybase.result import FatalError

from backup.settings import BackupSettings

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from backup.config import BackupConfig, BackupInstance
    from backup.step_result import StepResult



def _format_progress(event: ProgressEvent, elapsed: float) -> str:
    seconds = max(0, int(elapsed))
    progress = ""
    if event.phase == "archiving" and event.done_bytes is not None and event.total_bytes is not None and event.total_bytes > 0:
        percent = min(99, max(0, event.done_bytes * 100 // event.total_bytes))
        progress = f" [{percent}%]"
    return f"{event.label} {event.phase}{progress} {seconds // 60}:{seconds % 60:02}"


class _LiveProgress:
    def __init__(self) -> None:
        self.events = {}
        self.started = {}
        self.status = None
        self.running = False

    def on_progress(self, event: ProgressEvent) -> None:
        if event.label not in self.started:
            self.started[event.label] = time.monotonic()
        self.events[event.label] = event
        self.refresh()

    def refresh(self) -> None:
        if not self.events:
            return
        if self.status is None:
            self.status = console.status("")
        now = time.monotonic()
        message = Text(" | ".join(_format_progress(event, now - self.started[label]) for label, event in self.events.items()))
        self.status.update(message)
        if not self.running:
            self.status.start()
            self.running = True

    def finish(self, label: str) -> None:
        self.events.pop(label, None)
        self.started.pop(label, None)
        if self.events:
            self.refresh()
        elif self.running:
            self.status.stop()
            self.running = False

    def close(self) -> None:
        if self.running:
            self.status.stop()
            self.running = False


def _report_step(step: StepResult) -> None:
    if step.skipped:
        console.warning(f"{step.label}: {step.message}" if step.message else f"{step.label} skipped")
    elif step.success:
        console.success(f"{step.label}: {step.message}" if step.message else f"{step.label} archived")
    else:
        message = f"{step.label} cancelled" if step.message == "cancelled" else step.message
        console.failure(f"{step.label}: {message}" if message else f"{step.label} failed")


def _report_steps(
    steps: Iterable[StepResult], *, dry_run: bool = False, on_interrupt: Callable[[], None] | None = None,
    on_result: Callable[[StepResult], None] | None = None
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
    cfg: BackupConfig, plan: list[tuple[str, BackupInstance]], *, dry_run: bool, plan_only: bool, jobs: int = 3, quiet: bool = False
) -> bool:
    """Render the selected plan or drain its run, preserving interruption cleanup.

    Return whether the plan or run failed so the caller exits nonzero and cron
    sees a failed backup.
    """
    from backup.runner import Runner

    live = _LiveProgress() if sys.stdout.isatty() and not quiet and not dry_run and not plan_only else None
    try:
        runner = Runner(cfg, dry_run=dry_run, jobs=jobs,
                        on_progress=live.on_progress if live is not None else None,
                        on_tick=live.refresh if live is not None else None)
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
            failed = _report_steps(steps, dry_run=dry_run, on_interrupt=runner.request_cancel,
                                   on_result=(lambda step: live.finish(step.label)) if live is not None else None)
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
        return True
    finally:
        if live is not None:
            live.close()


@click.command(help="Run configured backup archives")
@click.option("--only", multiple=True, help="Run only these instance names (comma-separated or repeated).")
@click.option("--tag", "tags", multiple=True, help="Run only instances carrying one of these tags.")
@click.option("--list", "list_plan", is_flag=True, help="Print the configured instances and exit.")
@click.option("--plan", "plan_only", is_flag=True, help="Print the selected archive plan without walking sources.")
@click.option("--quiet", is_flag=True, help="Hide live progress; keep final results and the summary.")
@click.option("--dry-run", is_flag=True, help="Walk and report what would be archived without writing it.")
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

```

## Initial failed scaffold attempt

```text
...............F................                                         [100%]
=================================== FAILURES ===================================
E   AssertionError
/Users/bob/git/src/github.com/buvis/gems/tests/tools/backup/progress_cli_cases.py:252: AssertionError
=========================== short test summary info ============================
FAILED tests/tools/backup/test_progress.py::TestCliProgressRunPlan::test_cli_quiet_and_early_returns_never_create_live_status[--quiet]
1 failed, 31 passed, 89 deselected in 1.02s

EXIT_CODE 1

```

## Weak point 1: Summary counts hardcoded to zero

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -116,7 +116,7 @@
     verb = "previewed" if dry_run else "archived"
     while True:
         try:
-            console.info(f"{verb} {archived}, skipped {skipped}, failed {failed}")
+            console.info(f"{verb} 0, skipped 0, failed 0")
             break
         except KeyboardInterrupt:
             if on_interrupt is None:

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.80s

EXIT_CODE 0

```

Preventing assertion: Assert the literal summary archived 1, skipped 1, failed 1 instead of comparing output against another call to _report_steps.

## Weak point 2: Live runner drops idle tick callback

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -292,7 +292,7 @@
     try:
         runner = Runner(cfg, dry_run=dry_run, jobs=jobs,
                         on_progress=live.on_progress if live is not None else None,
-                        on_tick=live.refresh if live is not None else None)
+                        on_tick=None)
         if plan_only:
             entries = runner.plan(plan)
             for entry in entries:

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.29s

EXIT_CODE 0

```

Preventing assertion: Capture Runner constructor kwargs during an enabled TTY run and require callable on_progress and on_tick; advance a clock without new events and call on_tick.

## Weak point 3: Result severity always informational

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -73,12 +73,12 @@
 
 def _report_step(step: StepResult) -> None:
     if step.skipped:
-        console.warning(f"{step.label}: {step.message}" if step.message else f"{step.label} skipped")
+        console.info(f"{step.label}: {step.message}" if step.message else f"{step.label} skipped")
     elif step.success:
-        console.success(f"{step.label}: {step.message}" if step.message else f"{step.label} archived")
+        console.info(f"{step.label}: {step.message}" if step.message else f"{step.label} archived")
     else:
         message = f"{step.label} cancelled" if step.message == "cancelled" else step.message
-        console.failure(f"{step.label}: {message}" if message else f"{step.label} failed")
+        console.info(f"{step.label}: {message}" if message else f"{step.label} failed")
 
 
 def _report_steps(

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.27s

EXIT_CODE 0

```

Preventing assertion: Assert Rich plain output marker/severity for success, skipped and failure independently rather than deriving expected output from _report_steps itself.

## Weak point 4: Skipped results incorrectly count as failures

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -100,7 +100,7 @@
             if on_result is not None:
                 on_result(pending)
             _report_step(pending)
-            if not pending.success:
+            if not pending.success or pending.skipped:
                 failed += 1
             elif pending.skipped:
                 skipped += 1

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.24s

EXIT_CODE 0

```

Preventing assertion: Run one successful skipped StepResult, assert _report_steps returns False and summary archived 0, skipped 1, failed 0.

## Weak point 5: Percentages only correct for fixture byte pairs

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -26,7 +26,7 @@
     seconds = max(0, int(elapsed))
     progress = ""
     if event.phase == "archiving" and event.done_bytes is not None and event.total_bytes is not None and event.total_bytes > 0:
-        percent = min(99, max(0, event.done_bytes * 100 // event.total_bytes))
+        percent = {(37, 100): 37, (7, 19): 36, (100, 100): 99, (200, 100): 99, (3, 7): 42}.get((event.done_bytes, event.total_bytes), 0)
         progress = f" [{percent}%]"
     return f"{event.label} {event.phase}{progress} {seconds // 60}:{seconds % 60:02}"
 

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.28s

EXIT_CODE 0

```

Preventing assertion: Parametrize an additional byte ratio such as ProgressEvent('arbitrary', 'archiving', 25, 100), asserting 25%; use generated valid byte pairs.

## Weak point 6: Third concurrent progress label silently discarded

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -39,6 +39,8 @@
         self.running = False
 
     def on_progress(self, event: ProgressEvent) -> None:
+        if event.label not in self.events and len(self.events) >= 2:
+            return
         if event.label not in self.started:
             self.started[event.label] = time.monotonic()
         self.events[event.label] = event

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.20s

EXIT_CODE 0

```

Preventing assertion: Emit three concurrent labels without finishing any, assert all three exact labels remain in the rendered text and retain insertion order.

## Weak point 7: Dry-run summary falsely says archived

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -113,7 +113,7 @@
             if on_interrupt is None:
                 raise
             on_interrupt()
-    verb = "previewed" if dry_run else "archived"
+    verb = "archived"
     while True:
         try:
             console.info(f"{verb} {archived}, skipped {skipped}, failed {failed}")

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.21s

EXIT_CODE 0

```

Preventing assertion: Call _report_steps with dry_run=True and assert its summary uses previewed rather than archived.

## Weak point 8: Elapsed time resets on scanning-to-archiving transition

Exact isolated wrong implementation delta:

```diff
--- temporary-baseline/cli.py
+++ wrong/cli.py
@@ -39,7 +39,7 @@
         self.running = False
 
     def on_progress(self, event: ProgressEvent) -> None:
-        if event.label not in self.started:
+        if event.label not in self.started or (event.phase == 'archiving' and self.events[event.label].phase == 'scanning'):
             self.started[event.label] = time.monotonic()
         self.events[event.label] = event
         self.refresh()

```

Exact measured output:

```text
................................                                         [100%]
32 passed, 89 deselected in 0.19s

EXIT_CODE 0

```

Preventing assertion: Emit scanning at t=100 and archiving for the same label at t=165; assert archiving elapsed is 1:05 rather than 0:00.
