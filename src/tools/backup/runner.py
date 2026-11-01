from __future__ import annotations

import os
import queue
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from backup.capabilities import CAPABILITIES
from backup.capabilities.tar_archive import ArchiveCancelled
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from backup.config import BackupConfig, BackupInstance

__all__ = ["Runner"]


class Runner:
    """Execute selected backup instances, yielding a :class:`StepResult` per step.

    Each instance invokes its registered capability with the instance's ``with:``
    inputs plus the runtime context the capability needs: the resolved instance
    ``excludes`` list, the instance ``label``, and the ``dry_run`` flag. Under
    ``dry_run`` the capability itself previews (walks + reports) without writing.
    """

    def __init__(self: Runner, cfg: BackupConfig, *, dry_run: bool = False, jobs: int = 3) -> None:
        if jobs < 1:
            raise ValueError("jobs must be at least 1")
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._cancel: threading.Event | None = None
        self._cancelled: set[str] = set()
        self._cancelled_lock = threading.Lock()
        self.interrupted = False
        self.cancelled_names: tuple[str, ...] = ()

    def request_cancel(self: Runner) -> None:
        """Signal cancellation without waiting for workers or rendering output."""
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def run(self: Runner, selected: list[tuple[str, BackupInstance]]) -> Generator[StepResult, None, None]:
        self.interrupted = False
        self.cancelled_names = ()
        self._cancelled.clear()
        cancel = threading.Event()
        self._cancel = cancel
        now = datetime.now()
        ordered = sorted(selected, key=lambda item: (item[1].order, item[0]))
        remaining = deque(ordered)
        ready: deque[StepResult] = deque()
        try:
            try:
                entries = self._plan(selected, now)
                failures = {
                    name: entry.reason
                    for (name, _), entry in zip(selected, entries, strict=True)
                    if entry.status == "fail"
                }
                ready.extend(StepResult(name, success=False, message=reason) for name, reason in failures.items())
                remaining = deque((name, instance) for name, instance in ordered if name not in failures)
            except KeyboardInterrupt:
                self.request_cancel()

            yield from self._execute(remaining, ready, now, cancel)
        finally:
            self.cancelled_names = tuple(name for name, _ in ordered if name in self._cancelled)
            self._cancel = None

    def _execute(
        self: Runner,
        remaining: deque[tuple[str, BackupInstance]],
        ready: deque[StepResult],
        now: datetime,
        cancel: threading.Event,
    ) -> Iterator[StepResult]:
        completed: queue.Queue[Future[list[StepResult]]] = queue.Queue()
        pending: dict[Future[list[StepResult]], str] = {}
        outcomes: dict[str, list[StepResult]] = {}
        executor: ThreadPoolExecutor | None = None
        finished = False
        try:
            while ready or remaining or pending or outcomes:
                try:
                    if cancel.is_set():
                        if executor is not None:
                            self._shutdown(executor)
                            executor = None
                        names = dict.fromkeys((*pending.values(), *(name for name, _ in remaining)))
                        ready.extend(row for rows in outcomes.values() for row in rows)
                        ready.extend(self._cancelled_result(name) for name in names if name not in outcomes)
                        remaining.clear()
                        pending.clear()
                        outcomes.clear()
                    if ready:
                        yield ready.popleft()
                        continue

                    while remaining and len(pending) < self._jobs and not cancel.is_set():
                        if executor is None:
                            executor = ThreadPoolExecutor(max_workers=self._jobs)
                        name, instance = remaining[0]
                        future = executor.submit(self._run_instance, name, instance, now, cancel, outcomes)
                        pending[future] = name
                        remaining.popleft()
                        future.add_done_callback(completed.put)
                    if pending:
                        future = completed.get()
                        name = pending.pop(future)
                        ready.extend([self._cancelled_result(name)] if future.cancelled() else outcomes.pop(name))
                except KeyboardInterrupt:
                    self.request_cancel()
            finished = True
        finally:
            if not finished:
                cancel.set()
            if executor is not None:
                self._shutdown(executor)

    def _shutdown(self: Runner, executor: ThreadPoolExecutor) -> None:
        while True:
            try:
                executor.shutdown(wait=True, cancel_futures=True)
                return
            except KeyboardInterrupt:
                self.request_cancel()

    def _cancelled_result(self: Runner, name: str) -> StepResult:
        with self._cancelled_lock:
            self._cancelled.add(name)
        return StepResult(name, success=False, message="cancelled")

    def plan(self: Runner, selected: list[tuple[str, BackupInstance]]) -> list[PlanEntry]:
        return self._plan(selected, datetime.now())

    def _plan(self: Runner, selected: list[tuple[str, BackupInstance]], now: datetime) -> list[PlanEntry]:
        entries = []
        keys: list[str | None] = []
        outputs: dict[str, list[str]] = {}
        for name, instance in selected:
            capability = CAPABILITIES.get(instance.use)
            key: str | None = None
            if capability is None:  # pragma: no cover - load_config validates this
                entry = PlanEntry(name, "", "", "fail", f"unknown capability '{instance.use}'", False)
            else:
                call_kwargs: dict[str, object] = {
                    **instance.with_,
                    "label": name,
                    "excludes": list(effective_excludes(self._cfg, instance)),
                    "now": now,
                }
                try:
                    entry = capability.plan(**call_kwargs)
                except FatalError:
                    raise
                except Exception as exc:
                    # keep the configured output so duplicate detection still sees it
                    # (resolved with the run-wide timestamp, like the capability does)
                    configured = now.strftime(str(instance.with_.get("out", "")))
                    entry = PlanEntry(name, "", configured, "fail", f"{name} failed: {exc}", False)
                if entry.out:
                    key = os.path.normpath(os.path.expanduser(entry.out))
                    outputs.setdefault(key, []).append(name)
            entries.append(entry)
            keys.append(key)

        for index, (entry, out) in enumerate(zip(entries, keys, strict=True)):
            if out is not None and len(outputs[out]) > 1:
                names = outputs[out]
                others = ", ".join(sorted(name for name in names if name != entry.label))
                entries[index] = entry._replace(
                    out=out,
                    status="fail",
                    reason=f"output '{out}' is also the output of '{others}'",
                )
        return entries

    def _run_instance(
        self: Runner,
        name: str,
        instance: BackupInstance,
        now: datetime,
        cancel: threading.Event,
        outcomes: dict[str, list[StepResult]],
    ) -> list[StepResult]:
        if cancel.is_set():
            outcomes[name] = [self._cancelled_result(name)]
            return outcomes[name]
        capability = CAPABILITIES[instance.use]

        call_kwargs: dict[str, object] = {
            **instance.with_,
            "label": name,
            "excludes": list(effective_excludes(self._cfg, instance)),
            "dry_run": self._dry_run,
            "now": now,
            "cancel": cancel,
        }
        try:
            outcomes[name] = list(capability.run(**call_kwargs))
        except ArchiveCancelled:
            outcomes[name] = [self._cancelled_result(name)]
        except Exception as exc:
            outcomes[name] = [StepResult(name, success=False, message=f"{name} failed: {exc}")]
        return outcomes[name]
