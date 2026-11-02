from __future__ import annotations

import queue
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import pytest

from backup.capabilities.tar_archive import ArchiveCancelled
from backup.runner import Runner
from backup.step_result import StepResult
from tests.tools.backup.parallel_runner_helpers import WAIT, CapabilityProbe, Consumption, configure


def _interruptible_probe(*, wait_for_second: bool = False) -> CapabilityProbe:
    probe = CapabilityProbe(("omega", "alpha-copy", "alpha"))

    def run(kwargs: dict[str, Any]) -> Iterator[StepResult]:
        name = kwargs["label"]
        if name == "alpha":
            if wait_for_second:
                assert probe.started["alpha-copy"].wait(WAIT)
            yield StepResult(name, True, "complete alpha")
            return
        cancel = kwargs["cancel"]
        assert isinstance(cancel, threading.Event)
        assert cancel.wait(WAIT), f"worker {name} did not receive cancellation"
        raise ArchiveCancelled

    probe.behavior = run
    return probe


def _assert_terminal_results(runner: Runner, consumer: Consumption, probe: CapabilityProbe) -> None:
    assert Counter(row.label for row in consumer.results) == {"alpha": 1, "alpha-copy": 1, "omega": 1}
    results = {row.label: row for row in consumer.results}
    assert results["alpha"].success is True
    assert results["alpha"].message == "complete alpha"
    for name in ("alpha-copy", "omega"):
        assert results[name].success is False
        assert results[name].archive is None
        assert results[name].skipped is False
    assert runner.interrupted is True
    assert runner.cancelled_names == ("alpha-copy", "omega")
    assert not probe.started["omega"].is_set()
    assert probe.active == 0
    assert all(thread.ident not in probe.thread_ids for thread in threading.enumerate())
    for call in probe.calls:
        name = call["label"]
        assert call["source"] == f"/source/{name}"
        assert call["out"] == f"/output/{name}.tgz"
        assert call["token"] == f"token-{name}"


class TestRunnerInterruptBoundaries:
    def test_interrupt_after_dequeue_preserves_success_without_waiting_for_a_lost_notification(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = _interruptible_probe(wait_for_second=True)
        cfg = configure(monkeypatch, probe)
        dequeued = threading.Event()

        class InterruptingQueue(queue.Queue[Any]):
            def get(self, block: bool = True, timeout: float | None = None) -> Any:
                try:
                    item = super().get(block=block, timeout=WAIT if timeout is None else timeout)
                except queue.Empty:
                    raise AssertionError("cleanup waited for an already-dequeued completion") from None
                if not dequeued.is_set():
                    dequeued.set()
                    raise KeyboardInterrupt
                return item

        monkeypatch.setattr("backup.runner.queue.Queue", InterruptingQueue)
        runner = Runner(cfg, jobs=2)
        with Consumption(runner, cfg, probe) as consumer:
            consumer.finish()
        assert dequeued.is_set(), "test did not reach the dequeue boundary"
        assert probe.started["alpha-copy"].is_set()
        _assert_terminal_results(runner, consumer, probe)

    @pytest.mark.parametrize("worker_started", [False, True], ids=["before-submit", "after-worker-start"])
    def test_interrupt_during_submission_keeps_the_popped_instance_and_joins_workers(
        self, monkeypatch: pytest.MonkeyPatch, worker_started: bool
    ) -> None:
        probe = _interruptible_probe()
        cfg = configure(monkeypatch, probe)
        interrupted = threading.Event()

        class InterruptingExecutor(ThreadPoolExecutor):
            submissions = 0

            def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
                self.submissions += 1
                if self.submissions == 2:
                    if worker_started:
                        super().submit(fn, *args, **kwargs)
                        assert probe.started["alpha-copy"].wait(WAIT)
                    interrupted.set()
                    raise KeyboardInterrupt
                future = super().submit(fn, *args, **kwargs)
                future.result(timeout=WAIT)
                return future

        monkeypatch.setattr("backup.runner.ThreadPoolExecutor", InterruptingExecutor)
        runner = Runner(cfg, jobs=2)
        with Consumption(runner, cfg, probe) as consumer:
            consumer.finish()
        assert interrupted.is_set(), "test did not reach the submission boundary"
        assert probe.started["alpha-copy"].is_set() is worker_started
        _assert_terminal_results(runner, consumer, probe)

    def test_empty_selection_has_no_terminal_results_or_interruption(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probe = CapabilityProbe(())
        cfg = configure(monkeypatch, probe)
        runner = Runner(cfg, jobs=2)
        assert list(runner.run([])) == []
        assert runner.interrupted is False
        runner.request_cancel()
        runner.request_cancel()
        assert runner.interrupted is True
        assert runner.cancelled_names == ()
        assert probe.calls == []
