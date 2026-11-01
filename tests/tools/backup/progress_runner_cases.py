from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from typing import Any

import pytest

from backup.capabilities import CAPABILITIES
from backup.config import BackupConfig, BackupInstance
from backup.runner import Runner
from backup.step_result import PlanEntry, ProgressEvent, StepResult


def _frames(label: str, value: int = 7) -> list[ProgressEvent]:
    return [
        ProgressEvent(label, "scanning", None, None),
        ProgressEvent(label, "archiving", value, value + 31),
        ProgressEvent(label, "finalizing", value + 31, value + 31),
    ]


class _Capability:
    inputs: dict[str, object] = {}

    def __init__(self, produce: Callable[[dict[str, Any]], Iterator[StepResult]]) -> None:
        self.produce = produce
        self.calls: list[dict[str, Any]] = []
        self.plans: list[dict[str, Any]] = []

    def plan(self, **kwargs: Any) -> PlanEntry:
        self.plans.append(kwargs)
        label = kwargs["label"]
        return PlanEntry(label, f"/source/{label}", f"/archives/{label}.tar.gz", "run", "", False)

    def run(self, **kwargs: Any) -> Iterator[StepResult]:
        self.calls.append(kwargs)
        yield from self.produce(kwargs)


def _config(monkeypatch: pytest.MonkeyPatch, capability: _Capability, labels: tuple[str, ...]) -> BackupConfig:
    monkeypatch.setitem(CAPABILITIES, "controlled-progress", capability)
    return BackupConfig(
        instances={label: BackupInstance(use="controlled-progress", order=index) for index, label in enumerate(labels)},
        excludes=("cache", "cache-old"),
    )


def _outcomes(results: Iterator[StepResult] | list[StepResult]) -> list[tuple[str, bool, str]]:
    return [(result.label, result.success, result.message) for result in results]


def _blocking_waits(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, float | None]]:
    waits: list[tuple[int, float | None]] = []
    original_get = queue.Queue.get

    def get(instance: queue.Queue[Any], block: bool = True, timeout: float | None = None) -> Any:
        if block:
            waits.append((threading.get_ident(), timeout))
        return original_get(instance, block=block, timeout=timeout)

    monkeypatch.setattr(queue.Queue, "get", get)
    return waits


class _OrderedCapability(_Capability):
    def __init__(self, success: bool) -> None:
        super().__init__(self.produce_ordered)
        self.success = success
        self.emitted: list[ProgressEvent] = []
        self.worker_threads: list[int] = []
        self.old_done = threading.Event()

    def produce_ordered(self, kwargs: dict[str, Any]) -> Iterator[StepResult]:
        self.worker_threads.append(threading.get_ident())
        label = kwargs["label"]
        if label == "vault":
            assert self.old_done.wait(3), "second label was not submitted concurrently"
        for event in _frames(label, 7 if label == "vault" else 19):
            self.emitted.append(event)
            kwargs["progress"](event)
        if label == "vault-old":
            self.old_done.set()
        yield StepResult(label, self.success, f"{label}: {'stored' if self.success else 'failed'}")


class TestRunnerCallingThread:
    @pytest.mark.parametrize("background_consumer", [False, True])
    @pytest.mark.parametrize("success", [False, True])
    def test_runner_preserves_fifo_events_and_drains_before_results_on_calling_thread(
        self,
        monkeypatch: pytest.MonkeyPatch,
        background_consumer: bool,
        success: bool,
    ) -> None:
        received: list[ProgressEvent] = []
        observer_threads: list[int] = []

        def observe(event: ProgressEvent) -> None:
            observer_threads.append(threading.get_ident())
            received.append(event)

        capability = _OrderedCapability(success)
        cfg = _config(monkeypatch, capability, ("vault", "vault-old"))
        runner = Runner(cfg, jobs=2, on_progress=observe)

        def consume() -> tuple[int, list[StepResult]]:
            results = []
            for result in runner.run(list(cfg.instances.items())):
                expected = _frames(result.label, 7 if result.label == "vault" else 19)
                assert [event for event in received if event.label == result.label] == expected
                results.append(result)
            return threading.get_ident(), results

        with ThreadPoolExecutor(max_workers=1) as executor:
            caller, results = executor.submit(consume).result(timeout=5) if background_consumer else consume()
        assert received == capability.emitted == _frames("vault-old", 19) + _frames("vault", 7)
        assert observer_threads == [caller] * 6
        assert all(worker != caller for worker in capability.worker_threads)
        assert {result.label: (result.success, result.message) for result in results} == {
            label: (success, f"{label}: {'stored' if success else 'failed'}") for label in ("vault", "vault-old")
        }
        for call in capability.calls:
            assert call["progress"] is not observe
            assert call["excludes"] == ["cache", "cache-old"]
            assert not {"on_progress", "on_tick", "console"}.intersection(call)

    @pytest.mark.parametrize("with_observer", [False, True])
    def test_runner_ticks_without_events_and_isolates_each_observer_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
        with_observer: bool,
    ) -> None:
        release = threading.Event()
        events: list[ProgressEvent] = []
        ticks: list[int] = []
        waits = _blocking_waits(monkeypatch)

        def produce(kwargs: dict[str, Any]) -> Iterator[StepResult]:
            assert release.wait(3), "idle runner did not offer ticks"
            if kwargs["progress"] is not None:
                for event in _frames(kwargs["label"], 23):
                    kwargs["progress"](event)
            yield StepResult(kwargs["label"], True, "writer unaffected")

        def tick() -> None:
            ticks.append(threading.get_ident())
            if len(ticks) == 2:
                release.set()
            raise ValueError("broken elapsed observer")

        def observe(event: ProgressEvent) -> None:
            events.append(event)
            raise RuntimeError("broken progress observer")

        capability = _Capability(produce)
        cfg = _config(monkeypatch, capability, ("quiet",))
        runner = Runner(
            cfg,
            on_progress=observe if with_observer else None,
            on_tick=tick,
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                caller, results = executor.submit(
                    lambda: (threading.get_ident(), list(runner.run(list(cfg.instances.items()))))
                ).result(timeout=5)
        finally:
            release.set()
        assert _outcomes(results) == [("quiet", True, "writer unaffected")]
        assert events == (_frames("quiet", 23) if with_observer else [])
        assert len(ticks) >= 2
        assert set(ticks) == {caller}
        caller_waits = [timeout for thread, timeout in waits if thread == caller]
        assert len(caller_waits) >= 2
        assert all(timeout == 0.2 for timeout in caller_waits)


class TestRunnerSuppression:
    @pytest.mark.parametrize("dry_run,with_observer", [(True, True), (False, False)])
    def test_runner_passes_no_progress_for_dry_run_or_absent_observer(
        self,
        monkeypatch: pytest.MonkeyPatch,
        dry_run: bool,
        with_observer: bool,
    ) -> None:
        observed: list[ProgressEvent] = []
        ticks: list[int] = []

        def produce(kwargs: dict[str, Any]) -> Iterator[StepResult]:
            if dry_run:
                threading.Event().wait(0.45)
            yield StepResult(kwargs["label"], True, "preview" if dry_run else "stored")

        capability = _Capability(produce)
        cfg = _config(monkeypatch, capability, ("docs", "docs-old"))
        runner = Runner(
            cfg,
            dry_run=dry_run,
            on_progress=observed.append if with_observer else None,
            on_tick=lambda: ticks.append(1),
        )
        assert {result.label for result in runner.run(list(cfg.instances.items()))} == {"docs", "docs-old"}
        assert len(capability.calls) == 2
        assert all(call["progress"] is None and call["dry_run"] is dry_run for call in capability.calls)
        assert observed == []
        if dry_run:
            assert ticks == []

    def test_runner_plan_and_empty_configuration_never_invoke_callbacks(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        events: list[ProgressEvent] = []
        ticks: list[int] = []
        capability = _Capability(lambda _: iter(()))
        cfg = _config(monkeypatch, capability, ("docs", "docs-old"))
        runner = Runner(
            cfg,
            on_progress=events.append,
            on_tick=lambda: ticks.append(1),
        )
        assert {entry.label for entry in runner.plan(list(cfg.instances.items()))} == {"docs", "docs-old"}
        assert capability.calls == []
        assert len(capability.plans) == 2
        empty = Runner(BackupConfig(), on_progress=events.append, on_tick=lambda: ticks.append(1))
        assert list(empty.run([])) == []
        assert list(empty.plan([])) == []
        assert events == []
        assert ticks == []

    def test_runner_unknown_capability_yields_failure_without_fabricated_progress(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        events: list[ProgressEvent] = []

        def produce(kwargs: dict[str, Any]) -> Iterator[StepResult]:
            for event in _frames(kwargs["label"]):
                kwargs["progress"](event)
            yield StepResult(kwargs["label"], True, "stored")

        capability = _Capability(produce)
        cfg = _config(monkeypatch, capability, ("docs",))
        cfg = BackupConfig(instances={**cfg.instances, "docs-old": BackupInstance(use="controlled-progress-old")})
        runner = Runner(cfg, on_progress=events.append)
        results = {}
        for result in runner.run(list(cfg.instances.items())):
            results[result.label] = result
            if result.label == "docs":
                assert events == _frames("docs")
        assert results["docs"].success is True
        assert results["docs-old"].success is False
        assert results["docs-old"].message
        assert events == _frames("docs")
        assert [call["label"] for call in capability.calls] == ["docs"]


class TestRunnerCancellation:
    @pytest.mark.parametrize("interrupt", [False, True])
    def test_runner_drains_queued_prefix_when_observer_requests_cancel_or_interrupts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        interrupt: bool,
    ) -> None:
        queued = threading.Event()
        finished = threading.Event()
        received: list[ProgressEvent] = []

        def produce(kwargs: dict[str, Any]) -> Iterator[StepResult]:
            try:
                for event in _frames(kwargs["label"])[:2]:
                    kwargs["progress"](event)
                queued.set()
                assert kwargs["cancel"].wait(3), "cancellation did not reach capability"
                kwargs["progress"](_frames(kwargs["label"])[2])
                yield StepResult(kwargs["label"], False, "cancelled writer")
            finally:
                finished.set()

        def observe(event: ProgressEvent) -> None:
            received.append(event)
            if len(received) == 1:
                assert queued.wait(2)
                if interrupt:
                    raise KeyboardInterrupt
                runner.request_cancel()

        capability = _Capability(produce)
        cfg = _config(monkeypatch, capability, ("cancel-me",))
        runner = Runner(cfg, on_progress=observe)
        results = []
        for result in runner.run(list(cfg.instances.items())):
            assert received == _frames("cancel-me")[:2]
            assert finished.is_set()
            results.append(result)
        assert runner.interrupted is True
        assert [result.label for result in results] == ["cancel-me"]
        assert received == _frames("cancel-me")[:2]

    def test_runner_uses_fresh_progress_queue_for_each_run(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        received: list[ProgressEvent] = []
        previous_enqueues: list[Callable[[ProgressEvent], None]] = []

        def produce(kwargs: dict[str, Any]) -> Iterator[StepResult]:
            progress = kwargs["progress"]
            previous_enqueues.append(progress)
            for event in _frames(kwargs["label"], 7 if len(previous_enqueues) == 1 else 29):
                progress(event)
            yield StepResult(kwargs["label"], True, "stored")

        capability = _Capability(produce)
        cfg = _config(monkeypatch, capability, ("same-label",))
        runner = Runner(cfg, on_progress=received.append)
        assert _outcomes(runner.run(list(cfg.instances.items()))) == [("same-label", True, "stored")]
        assert received == _frames("same-label", 7)
        previous_enqueues[0](ProgressEvent("same-label-old", "archiving", 999, 1000))
        received.clear()
        assert _outcomes(runner.run(list(cfg.instances.items()))) == [("same-label", True, "stored")]
        assert received == _frames("same-label", 29)
        assert previous_enqueues[0] is not previous_enqueues[1]


class _FloodCapability(_Capability):
    def __init__(self) -> None:
        super().__init__(self.produce_flood)
        self.start = threading.Event()
        self.full = threading.Event()
        self.overflow_attempt = threading.Event()
        self.overflow_returned = threading.Event()
        self.finished = threading.Event()
        self.cancel_seen = threading.Event()
        self.tick_delivered = threading.Event()
        self.enqueued: list[ProgressEvent] = []

    def produce_flood(self, kwargs: dict[str, Any]) -> Iterator[StepResult]:
        label = kwargs["label"]
        if label == "first":
            yield StepResult(label, True, "first finished")
            return
        try:
            assert self.start.wait(3), "consumer did not release producer"
            for number in range(257):
                if number == 256:
                    self.full.set()
                    self.overflow_attempt.set()
                event = ProgressEvent(label, "archiving", number, 257)
                kwargs["progress"](event)
                self.enqueued.append(event)
            self.overflow_returned.set()
            if kwargs["cancel"].is_set():
                self.cancel_seen.set()
                kwargs["progress"](ProgressEvent("flood-old", "finalizing", 257, 257))
            yield StepResult(label, True, "flood finished")
        finally:
            self.finished.set()


def _suspend_flood(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_FloodCapability, Runner, Iterator[StepResult], list[ProgressEvent]]:
    capability = _FloodCapability()
    received: list[ProgressEvent] = []
    cfg = _config(monkeypatch, capability, ("first", "flood"))
    runner = Runner(
        cfg,
        jobs=2,
        on_progress=received.append,
        on_tick=capability.tick_delivered.set,
    )
    iterator = runner.run(list(cfg.instances.items()))
    assert _outcomes([next(iterator)]) == [("first", True, "first finished")]
    capability.tick_delivered.clear()
    capability.start.set()
    return capability, runner, iterator, received


def _assert_queue_backpressure(capability: _FloodCapability) -> None:
    assert capability.full.wait(2)
    assert capability.overflow_attempt.wait(2)
    assert not capability.overflow_returned.wait(0.45), "the 257th event bypassed bounded backpressure"
    assert len(capability.enqueued) == 256
    assert not capability.tick_delivered.is_set(), "ticks ran while the consumer held a yielded result"


class TestRunnerBoundedQueue:
    def test_runner_drains_full_queue_without_waiting_for_a_completed_future(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        capability, _runner, iterator, received = _suspend_flood(monkeypatch)
        with closing(iterator):
            _assert_queue_backpressure(capability)
            assert received == []
            remaining = []
            for result in iterator:
                assert received == [ProgressEvent("flood", "archiving", number, 257) for number in range(257)]
                remaining.append(result)
        assert _outcomes(remaining) == [("flood", True, "flood finished")]
        assert capability.finished.is_set()
        assert capability.overflow_returned.is_set()
        assert capability.cancel_seen.is_set() is False

    def test_runner_cancel_unblocks_backpressure_and_drains_every_previously_queued_event(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        capability, runner, iterator, received = _suspend_flood(monkeypatch)
        with closing(iterator):
            _assert_queue_backpressure(capability)
            runner.request_cancel()
            assert capability.overflow_returned.wait(2), "cancelled enqueue kept retrying a full queue"
            assert capability.finished.wait(2)
            remaining = []
            for result in iterator:
                assert received == [ProgressEvent("flood", "archiving", number, 257) for number in range(256)]
                remaining.append(result)
        assert [result.label for result in remaining] == ["flood"]
        assert runner.interrupted is True
        assert capability.cancel_seen.is_set()

    def test_runner_abandonment_cancels_before_join_and_never_calls_observers_in_finally(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        capability, runner, iterator, received = _suspend_flood(monkeypatch)
        closed = threading.Event()
        rescue_needed = threading.Event()

        def rescue_blocked_close() -> None:
            if not closed.wait(1.5):
                rescue_needed.set()
                runner.request_cancel()

        _assert_queue_backpressure(capability)
        rescue = threading.Thread(target=rescue_blocked_close, daemon=True)
        rescue.start()
        try:
            iterator.close()
        finally:
            closed.set()
            runner.request_cancel()
            rescue.join(timeout=2)
        assert not rescue_needed.is_set(), "abandonment joined a producer before cancelling its enqueue"
        assert capability.finished.is_set()
        assert capability.cancel_seen.is_set()
        assert received == []
