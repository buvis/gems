from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from sysup.capabilities import CAPABILITIES
from sysup.capabilities.sudo import SudoPrime
from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sysup.config import SysupCommand, SysupConfig

__all__ = ["Runner"]


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

    def run(self: Runner, selected: list[tuple[str, SysupCommand]]) -> Iterator[StepResult]:
        """Run ``selected`` (name, command) entries in the given order.

        Under ``dry_run`` nothing is executed: prime is skipped, no refresher is
        started, and no subprocess is spawned — each entry yields a synthetic
        "would run" step instead.
        """
        stops: list[Callable[[], None]] = []
        try:
            if not self._dry_run:
                stops = self._prime()
            for name, command in selected:
                yield from self._run_entry(name, command)
        finally:
            for stop in stops:
                stop()

    def _prime(self: Runner) -> list[Callable[[], None]]:
        stops: list[Callable[[], None]] = []
        for name in self._cfg.prime:
            capability = CAPABILITIES.get(name)
            if isinstance(capability, SudoPrime):
                stops.append(capability.prime())
        return stops

    def _run_entry(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
        if command.use is not None:
            yield from self._run_use(name, command)
        else:
            yield from self._run_steps(name, command)

    def _run_use(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
        capability = CAPABILITIES[command.use] if command.use is not None else None
        if capability is None:  # pragma: no cover - load_config validates this
            yield StepResult(name, success=False, message=f"unknown capability '{command.use}'")
            return

        if self._dry_run:
            yield StepResult(name, success=True, message=f"would run capability '{command.use}'")
            return

        try:
            yield from capability.run(**command.with_)
        except FatalError:
            raise
        except Exception as exc:
            yield StepResult(name, success=False, message=f"{name} failed: {exc}")

    def _run_steps(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
        steps = command.steps or ()

        if self._dry_run:
            rendered = "; ".join(" ".join(step) for step in steps)
            yield StepResult(name, success=True, message=f"would run: {rendered}")
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
            yield StepResult(name, success=True)

    def _run_argv(self: Runner, name: str, argv: list[str], command: SysupCommand) -> StepResult:
        if not argv:
            return StepResult(name, success=False, message="empty step")

        binary = argv[0]
        binary_path = shutil.which(binary)
        if binary_path is None:
            return StepResult(name, success=False, message=f"{binary} not found, skipping")
        resolved = [binary_path, *argv[1:]]

        if command.interactive:
            interactive_result = subprocess.run(resolved, check=False, timeout=command.timeout)
            if interactive_result.returncode == 0:
                return StepResult(name, success=True)
            return StepResult(
                name,
                success=False,
                message=f"{name} failed: exit code {interactive_result.returncode}",
            )

        result = subprocess.run(
            resolved,
            capture_output=True,
            text=True,
            check=False,
            timeout=command.timeout,
        )
        if result.returncode == 0:
            return StepResult(name, success=True)
        message = result.stderr.strip() or "unknown error"
        return StepResult(name, success=False, message=f"{name} failed: {message}")
