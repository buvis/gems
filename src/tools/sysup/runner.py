from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from sysup.capabilities import CAPABILITIES, EXPIRY_CAPABILITIES
from sysup.capabilities.sudo import SudoPrime
from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sysup.config import ExpiryItem, SysupCommand, SysupConfig

__all__ = ["Runner", "classify_expiry"]


def classify_expiry(name: str, outcome: datetime | str, warn_days: int, now: datetime) -> StepResult:
    if isinstance(outcome, str):
        return StepResult(
            name, success=False, message=f"{name}: unknown, {outcome}", status="unknown", command=name, kind="item"
        )
    day = outcome.astimezone(timezone.utc).date().isoformat()
    if outcome <= now:
        return StepResult(
            name, success=False, message=f"{name}: expired on {day}", status="expired", command=name, kind="item"
        )
    days_left = (outcome.astimezone(timezone.utc).date() - now.astimezone(timezone.utc).date()).days
    if days_left <= warn_days:
        return StepResult(
            name,
            success=True,
            message=f"{name}: expiring in {days_left} days ({day})",
            status="expiring",
            command=name,
            kind="item",
        )
    return StepResult(
        name, success=True, message=f"{name}: ok, expires {day} ({days_left} days)", command=name, kind="item"
    )


class Runner:
    """Execute ordered updater entries, yielding a :class:`StepResult` per step.

    Runs ``prime`` capabilities (e.g. sudo) before any command and releases them
    in a ``finally`` around the whole run so a ``KeyboardInterrupt`` between
    entries cannot leak a refresher thread. ``run`` entries execute their argv
    steps with early-abort (unless ``continue_on_error``); ``use`` entries invoke
    a registered capability. Binaries are re-resolved via :func:`shutil.which`
    immediately before each spawn.
    """

    def __init__(self: Runner, cfg: SysupConfig, *, dry_run: bool = False) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._item_status: dict[str, str] = {}

    def run(self: Runner, selected: list[tuple[str, SysupCommand]]) -> Iterator[StepResult]:
        """Run ``selected`` (name, command) entries in the given order.

        Under ``dry_run`` nothing is executed: prime is skipped, no refresher is
        started, and no subprocess is spawned — each entry yields a synthetic
        "would run" step instead.
        """
        stops: list[Callable[[], None]] = []
        try:
            if not self._dry_run:
                from sysup.config import applicable_items

                yield from self.check_items(applicable_items(self._cfg))
                stops = self._prime()
            for name, command in selected:
                yield from self._run_entry(name, command)
        finally:
            for stop in stops:
                stop()

    def check_items(self: Runner, items: list[tuple[str, ExpiryItem]]) -> Iterator[StepResult]:
        """Probe each expiry item, yielding one :class:`StepResult` per item.

        Records each item's status in ``self._item_status`` so ``needs:`` gating
        in :meth:`_run_entry` can read it. A capability returning a string, or
        raising anything other than :class:`FatalError`, becomes an ``unknown``
        step; ``FatalError`` propagates. Public so ``sysup refresh`` can re-check
        a single item.
        """
        now = datetime.now(timezone.utc)
        for name, item in items:
            capability = EXPIRY_CAPABILITIES[item.use]
            try:
                outcome = capability.expires_at(**item.with_)
            except FatalError:
                raise
            except Exception as exc:
                outcome = f"{type(exc).__name__}: {exc}"
            step = classify_expiry(name, outcome, item.warn_days, now)
            self._item_status[name] = step.status
            yield step

    def _prime(self: Runner) -> list[Callable[[], None]]:
        stops: list[Callable[[], None]] = []
        for name in self._cfg.prime:
            capability = CAPABILITIES.get(name)
            if isinstance(capability, SudoPrime):
                stops.append(capability.prime())
        return stops

    def _run_entry(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
        for item in command.needs:
            status = self._item_status.get(item)
            if status in ("expired", "unknown"):
                yield StepResult(
                    name,
                    success=False,
                    message=f"{name} skipped: {item} is {status}; run: sysup refresh {item}",
                    command=name,
                )
                return
        if command.use is not None:
            yield from self._run_use(name, command)
        else:
            yield from self._run_steps(name, command)

    def _run_use(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
        capability = CAPABILITIES[command.use] if command.use is not None else None
        if capability is None:  # pragma: no cover - load_config validates this
            yield StepResult(name, success=False, message=f"unknown capability '{command.use}'", command=name)
            return

        if self._dry_run:
            yield StepResult(name, success=True, message=f"would run capability '{command.use}'", command=name)
            return

        try:
            for step in capability.run(**command.with_):
                yield replace(step, command=name)
        except FatalError:
            raise
        except Exception as exc:
            yield StepResult(name, success=False, message=f"{name} failed: {exc}", command=name)

    def _run_steps(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
        steps = command.steps or ()

        if self._dry_run:
            rendered = "; ".join(" ".join(step) for step in steps)
            yield StepResult(name, success=True, message=f"would run: {rendered}", command=name)
            return

        ok = True
        for argv in steps:
            result = self._run_argv(name, list(argv), command)
            if not result.success:
                yield result
                ok = False
                if not command.continue_on_error:
                    return
            elif command.continue_on_error:
                yield result
        if ok and not command.continue_on_error:
            yield StepResult(name, success=True, command=name)

    def _run_argv(self: Runner, name: str, argv: list[str], command: SysupCommand) -> StepResult:
        if not argv:
            return StepResult(name, success=False, message="empty step", command=name)

        binary = argv[0]
        binary_path = shutil.which(binary)
        if binary_path is None:
            return StepResult(name, success=False, message=f"{binary} not found, skipping", command=name)
        resolved = [binary_path, *argv[1:]]

        if command.interactive:
            interactive_result = subprocess.run(resolved, check=False, timeout=command.timeout)
            if interactive_result.returncode == 0:
                return StepResult(name, success=True, command=name)
            return StepResult(
                name,
                success=False,
                message=f"{name} failed: exit code {interactive_result.returncode}",
                command=name,
            )

        result = subprocess.run(
            resolved,
            capture_output=True,
            text=True,
            check=False,
            timeout=command.timeout,
        )
        if result.returncode == 0:
            return StepResult(name, success=True, command=name)
        message = result.stderr.strip() or "unknown error"
        return StepResult(name, success=False, message=f"{name} failed: {message}", command=name)
