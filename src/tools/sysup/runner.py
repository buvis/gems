from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from buvis.pybase.adapters import console
from buvis.pybase.result import FatalError

from sysup import runlog
from sysup.capabilities import CAPABILITIES, EXPIRY_CAPABILITIES
from sysup.capabilities.sudo import SudoPrime
from sysup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from sysup.config import ExpiryItem, StepSpec, SysupCommand, SysupConfig
    from sysup.runlog import RunLog

__all__ = ["Runner", "classify_expiry"]

_MAX_PRINTED_ERRORS = 5
_ERROR_LINE = re.compile(r"^\s*error:", re.IGNORECASE)
# `sudo` as its own word, also right after a shell separator (`;sudo`, `&&sudo`,
# `|sudo`, `$(sudo`); over-matching only costs a spare password prompt.
_SUDO_WORD = re.compile(r"(^|[\s;&|(`])sudo($|[\s;&|)])")


def _scan_errors(stdout: str, stderr: str) -> list[str]:
    return [line for text in (stdout, stderr) for line in text.splitlines() if _ERROR_LINE.match(line)]


def _should_prime(selected: list[tuple[str, SysupCommand]]) -> bool:
    def _needs_sudo(command: SysupCommand) -> bool:
        return command.sudo or any(_SUDO_WORD.search(step.label) for step in (command.steps or ()))

    return sys.stdin.isatty() and any(_needs_sudo(command) for _, command in selected)


@dataclass(frozen=True)
class _ArgvOutcome:
    result: StepResult
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    timeout_s: float | None = None


def _as_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode(errors="replace")


def _run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """``subprocess.run`` whose timeout stops the whole step, not bash alone.

    A captured step with a timeout gets its own process group, so a
    multi-command shell line dies as one; Ctrl-C is forwarded to that group
    because the terminal no longer signals it. Everything else stays in the
    terminal's group: an interactive step must read the tty, and without a
    timeout there is nothing to kill. A command running as root through sudo
    cannot be signaled by a plain user and survives either way.
    """
    # ponytail: root members survive; `sudo -n kill -- -<pgid>` would reach
    # them off the primed ticket if that ever matters.
    timeout = kwargs.pop("timeout", None)
    kwargs.pop("check", None)
    capture = kwargs.pop("capture_output", False)
    if capture:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    own_group = capture and timeout is not None and sys.platform != "win32"
    with subprocess.Popen(argv, process_group=0 if own_group else None, **kwargs) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except BaseException as exc:
            if own_group:
                sig = signal.SIGINT if isinstance(exc, KeyboardInterrupt) else signal.SIGKILL
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(proc.pid, sig)
            proc.kill()
            raise
    return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)


def _timeout_outcome(name: str, timeout: float | None, exc: subprocess.TimeoutExpired) -> _ArgvOutcome:
    return _ArgvOutcome(
        result=StepResult(name, success=False, message=f"{name} timed out after {timeout}s", command=name),
        stdout=_as_text(exc.stdout),
        stderr=_as_text(exc.stderr),
        exit_code=None,
        timed_out=True,
        timeout_s=timeout,
    )


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
        self._log: RunLog | None = None
        self.log_path: Path | None = None

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
                if _should_prime(selected):
                    stops = self._prime()
                runlog.prune(runlog.logs_dir())
                self._log = runlog.open_run_log(
                    start=datetime.now(timezone.utc), plan_names=[name for name, _ in selected]
                )
                self.log_path = self._log.path
            for name, command in selected:
                yield from self._run_entry(name, command)
        finally:
            for stop in stops:
                with contextlib.suppress(BaseException):
                    stop()
            if self._log is not None:
                runlog.close(self._log)

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
        if capability is None or command.use is None:  # pragma: no cover - load_config validates this
            yield StepResult(name, success=False, message=f"unknown capability '{command.use}'", command=name)
            return

        if self._dry_run:
            yield StepResult(name, success=True, message=f"would run capability '{command.use}'", command=name)
            return

        try:
            with console.status(f"{name}: {command.use}"):
                for step in capability.run(**command.with_):
                    stamped = replace(step, command=name)
                    if self._log is not None:
                        runlog.append_step(self._log, name, command.use, captured=False, status=stamped.status)
                    yield stamped
        except FatalError:
            raise
        except Exception as exc:
            failed = StepResult(name, success=False, message=f"{name} failed: {exc}", command=name)
            if self._log is not None:
                runlog.append_step(self._log, name, command.use, captured=False, status=failed.status)
            yield failed

    def _run_steps(self: Runner, name: str, command: SysupCommand) -> Iterator[StepResult]:
        steps = command.steps or ()

        if self._dry_run:
            rendered = "; ".join(step.label for step in steps)
            yield StepResult(name, success=True, message=f"would run: {rendered}", command=name)
            return

        failures: list[StepResult] = []
        error_count = 0
        for step in steps:
            outcome = self._run_argv(name, step, command)
            if self._log is not None:
                really_captured = not command.interactive and (outcome.exit_code is not None or outcome.timed_out)
                runlog.append_step(
                    self._log,
                    name,
                    step.label,
                    captured=really_captured,
                    status=outcome.result.status,
                    exit_code=outcome.exit_code,
                    stdout=outcome.stdout,
                    stderr=outcome.stderr,
                    timed_out=outcome.timed_out,
                    timeout_s=outcome.timeout_s,
                )
            if not outcome.result.success:
                failures.append(outcome.result)
                if not command.continue_on_error:
                    yield outcome.result
                    return
                console.failure(outcome.result.message or f"{name}: step failed")
                continue
            errors = _scan_errors(outcome.stdout, outcome.stderr)
            error_count += len(errors)
            for line in errors[:_MAX_PRINTED_ERRORS]:
                console.failure(line)
            if len(errors) > _MAX_PRINTED_ERRORS:
                console.failure(f"+{len(errors) - _MAX_PRINTED_ERRORS} more, see log")
        if failures:
            message = "; ".join(f.message or f"{name}: step failed" for f in failures)
            yield StepResult(name, success=False, message=message, command=name)
        elif error_count:
            message = f"{name}: {error_count} error line(s), see log"
            yield StepResult(name, success=True, message=message, status="warned", command=name)
        else:
            yield StepResult(name, success=True, command=name)

    def _run_argv(self: Runner, name: str, step: StepSpec, command: SysupCommand) -> _ArgvOutcome:
        binary = step.argv[0]
        binary_path = shutil.which(binary)
        if binary_path is None:
            return _ArgvOutcome(
                result=StepResult(name, success=False, message=f"{binary} not found, skipping", command=name)
            )
        resolved = [binary_path, *step.argv[1:]]
        env = step.child_env()
        label = f"{name}: {step.label}"
        status_cm = contextlib.nullcontext() if command.interactive else console.status(label)

        if command.interactive:
            return self._run_argv_interactive(name, resolved, env, command, status_cm)
        return self._run_argv_captured(name, resolved, env, command, status_cm)

    def _run_argv_interactive(
        self: Runner,
        name: str,
        resolved: list[str],
        env: dict[str, str],
        command: SysupCommand,
        status_cm: contextlib.AbstractContextManager[object],
    ) -> _ArgvOutcome:
        with status_cm:
            try:
                interactive_result = _run(resolved, check=False, timeout=command.timeout, env=env)
            except subprocess.TimeoutExpired as exc:
                return _timeout_outcome(name, command.timeout, exc)
        if interactive_result.returncode == 0:
            return _ArgvOutcome(result=StepResult(name, success=True, command=name))
        return _ArgvOutcome(
            result=StepResult(
                name,
                success=False,
                message=f"{name} failed: exit code {interactive_result.returncode}",
                command=name,
            )
        )

    def _run_argv_captured(
        self: Runner,
        name: str,
        resolved: list[str],
        env: dict[str, str],
        command: SysupCommand,
        status_cm: contextlib.AbstractContextManager[object],
    ) -> _ArgvOutcome:
        with status_cm:
            try:
                proc = _run(resolved, capture_output=True, text=True, check=False, timeout=command.timeout, env=env)
            except subprocess.TimeoutExpired as exc:
                return _timeout_outcome(name, command.timeout, exc)
        if proc.returncode == 0:
            result = StepResult(name, success=True, command=name)
        else:
            message = proc.stderr.strip() or "unknown error"
            result = StepResult(name, success=False, message=f"{name} failed: {message}", command=name)
        return _ArgvOutcome(result=result, stdout=proc.stdout, stderr=proc.stderr, exit_code=proc.returncode)
