from __future__ import annotations

import os
import queue
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime
from functools import partial
from pathlib import Path

# Separate binding on purpose: tests monkeypatch ``backup.runner.queue.Queue`` to
# inject the completion queue; the progress queue must not be replaced with it.
from queue import Queue as ProgressQueue
from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from backup.capabilities import CAPABILITIES
from backup.capabilities.tar_archive import ArchiveCancelled, resolve_paths
from backup.config import effective_excludes
from backup.step_result import PlanEntry, ProgressEvent, StepResult

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator

    from backup.config import BackupConfig, BackupInstance

__all__ = ["Runner"]


def _enqueue_progress(events: ProgressQueue[ProgressEvent], cancel: threading.Event, event: ProgressEvent) -> None:
    while not cancel.is_set():
        try:
            events.put(event, timeout=0.2)
            return
        except queue.Full:
            continue


def _failed_plan_entry(name: str, instance: BackupInstance, now: datetime, error: Exception) -> PlanEntry:
    """Retain best-effort paths without letting metadata recovery fail again."""
    source_raw, out_raw = instance.with_.get("source", ""), instance.with_.get("out", "")
    source = source_raw if isinstance(source_raw, str) else ""
    out = out_raw if isinstance(out_raw, str) else ""
    with suppress(Exception):
        source = str(resolve_paths(source, "", now)[0]) if source else ""
    with suppress(Exception):
        out = str(resolve_paths("", out, now)[1]) if out else ""
    replaces = False
    if out:
        with suppress(Exception):
            replaces = Path(out).exists()
    return PlanEntry(name, source, out, "fail", f"{name} failed: {error}", replaces)


class Runner:
    """Execute selected backup instances, yielding a :class:`StepResult` per step.

    Each instance invokes its registered capability with the instance's ``with:``
    inputs plus the runtime context the capability needs: the resolved instance
    ``excludes`` list, the instance ``label``, and the ``dry_run`` flag. Under
    ``dry_run`` the capability itself previews (walks + reports) without writing.

    Observer callbacks (both optional):

    * ``on_progress(event)`` receives each :class:`ProgressEvent`.
    * ``on_tick()`` fires when no step has completed for 0.2 s, so a UI can
      redraw while workers are busy.

    Both run on the thread that iterates :meth:`run`, never on a worker. They
    fire only while the generator is being advanced, so none are delivered
    while it is paused at a ``yield``. Ordinary exceptions raised by a callback
    are swallowed. Callbacks must be short and nonblocking, as they stall the
    iterating thread. Neither fires under ``dry_run``, and the planning phase
    emits none.
    """

    def __init__(
        self: Runner,
        cfg: BackupConfig,
        *,
        dry_run: bool = False,
        jobs: int = 3,
        on_progress: Callable[[ProgressEvent], None] | None = None,
        on_tick: Callable[[], None] | None = None,
    ) -> None:
        if jobs < 1:
            raise ValueError("jobs must be at least 1")
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
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
        events: ProgressQueue[ProgressEvent] = ProgressQueue(maxsize=256)
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

            yield from self._execute(remaining, ready, now, cancel, events)
        finally:
            self.cancelled_names = tuple(name for name, _ in ordered if name in self._cancelled)
            self._cancel = None

    def _execute(
        self: Runner,
        remaining: deque[tuple[str, BackupInstance]],
        ready: deque[StepResult],
        now: datetime,
        cancel: threading.Event,
        events: ProgressQueue[ProgressEvent],
    ) -> Iterator[StepResult]:
        completed: queue.Queue[Future[list[StepResult]]] = queue.Queue()
        pending: dict[Future[list[StepResult]], str] = {}
        outcomes: dict[str, list[StepResult]] = {}
        executor: ThreadPoolExecutor | None = None
        finished = False
        progress: Callable[[ProgressEvent], None] | None = None
        if self._on_progress is not None and not self._dry_run:
            progress = partial(_enqueue_progress, events, cancel)
        try:
            while ready or remaining or pending or outcomes:
                try:
                    self._drain_progress(events)
                    if cancel.is_set():
                        if executor is not None:
                            self._shutdown(executor)
                            executor = None
                        self._drain_progress(events)
                        ready.extend(self._cancel_remaining(remaining, pending, outcomes))
                    if ready:
                        yield ready.popleft()
                        continue

                    while remaining and len(pending) < self._jobs and not cancel.is_set():
                        if executor is None:
                            executor = ThreadPoolExecutor(max_workers=self._jobs)
                        name, instance = remaining[0]
                        future = executor.submit(self._run_instance, name, instance, now, cancel, outcomes, progress)
                        pending[future] = name
                        remaining.popleft()
                        future.add_done_callback(completed.put)
                    if pending:
                        ready.extend(self._collect_completion(completed, pending, outcomes, events))
                except KeyboardInterrupt:
                    self.request_cancel()
            finished = True
        finally:
            if not finished:
                cancel.set()
            if executor is not None:
                self._shutdown(executor)

    def _drain_progress(self: Runner, events: ProgressQueue[ProgressEvent]) -> None:
        while True:
            try:
                event = events.get_nowait()
            except queue.Empty:
                return
            if self._on_progress is not None and not self._dry_run:
                with suppress(Exception):
                    self._on_progress(event)

    def _collect_completion(
        self: Runner,
        completed: queue.Queue[Future[list[StepResult]]],
        pending: dict[Future[list[StepResult]], str],
        outcomes: dict[str, list[StepResult]],
        events: ProgressQueue[ProgressEvent],
    ) -> list[StepResult]:
        self._drain_progress(events)
        try:
            future = completed.get(timeout=0.2)
        except queue.Empty:
            self._drain_progress(events)
            if self._on_tick is not None and not self._dry_run:
                with suppress(Exception):
                    self._on_tick()
            return []
        self._drain_progress(events)
        name = pending.pop(future)
        return [self._cancelled_result(name)] if future.cancelled() else outcomes.pop(name)

    def _cancel_remaining(
        self: Runner,
        remaining: deque[tuple[str, BackupInstance]],
        pending: dict[Future[list[StepResult]], str],
        outcomes: dict[str, list[StepResult]],
    ) -> list[StepResult]:
        names = dict.fromkeys((*pending.values(), *(name for name, _ in remaining)))
        rows = [row for results in outcomes.values() for row in results]
        rows.extend(self._cancelled_result(name) for name in names if name not in outcomes)
        remaining.clear()
        pending.clear()
        outcomes.clear()
        return rows

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
                    entry = _failed_plan_entry(name, instance, now, exc)
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

    def _run_instance(  # noqa: PLR0913, PLR0917 - preserve optional outcome context and capability progress contract
        self: Runner,
        name: str,
        instance: BackupInstance,
        now: datetime,
        cancel: threading.Event,
        outcomes: dict[str, list[StepResult]] | None = None,
        progress: Callable[[ProgressEvent], None] | None = None,
    ) -> list[StepResult]:
        if outcomes is None:
            outcomes = {}
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
            "progress": progress,
        }
        try:
            outcomes[name] = list(capability.run(**call_kwargs))
        except ArchiveCancelled:
            outcomes[name] = [self._cancelled_result(name)]
        except Exception as exc:
            outcomes[name] = [StepResult(name, success=False, message=f"{name} failed: {exc}")]
        return outcomes[name]
