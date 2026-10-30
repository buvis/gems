from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import datetime

import pytest
from buvis.pybase.result import FatalError

from backup.runner import Runner
from backup.step_result import PlanEntry, StepResult
from tests.tools.backup.parallel_runner_helpers import WAIT, CapabilityProbe, configure


class TestParallelRunnerLifecycle:
    @pytest.mark.parametrize("dry_run", [False, True])
    def test_workers_share_run_event_and_clock_without_mutating_instance_kwargs(
        self, monkeypatch: pytest.MonkeyPatch, dry_run: bool
    ) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy"))
        cfg = configure(monkeypatch, probe)
        original = {name: ["global-exclude", f"{name}-exclude"] for name in cfg.instances}

        def mutate_local(kwargs: dict[str, object]) -> Iterator[StepResult]:
            excludes = kwargs["excludes"]
            assert isinstance(excludes, list)
            excludes.append(str(kwargs["label"]))
            yield StepResult(str(kwargs["label"]), True)

        probe.behavior = mutate_local
        results = list(Runner(cfg, dry_run=dry_run, jobs=2).run(list(cfg.instances.items())))
        assert len(results) == 2 and all(row.success for row in results)
        first, second = probe.calls
        assert isinstance(first["cancel"], threading.Event)
        assert first["cancel"] is second["cancel"] and not first["cancel"].is_set()
        assert isinstance(first["now"], datetime)
        assert first["now"] == second["now"]
        assert all(plan["now"] == first["now"] for plan in probe.plans)
        assert first["excludes"] is not second["excludes"]
        for call in probe.calls:
            name = call["label"]
            assert call["token"] == f"token-{name}"
            assert call["source"] == f"/source/{name}"
            assert call["out"] == f"/output/{name}.tgz"
            assert call["dry_run"] is dry_run
            assert call["excludes"] == [*original[name], name]
            assert cfg.instances[name].exclude_add == [f"{name}-exclude"]
            assert cfg.excludes == ["global-exclude"]

    @pytest.mark.parametrize("dry_run", [False, True])
    def test_instance_runtime_values_override_with_options_and_pre_cancel_prevents_invocation(
        self, monkeypatch: pytest.MonkeyPatch, dry_run: bool
    ) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy"))
        cfg = configure(monkeypatch, probe)
        runner = Runner(cfg, dry_run=dry_run)
        cancel = threading.Event()
        now = datetime(2027, 2, 3, 4, 5, 6)
        probe.release_all()
        for name, instance in cfg.instances.items():
            instance.with_.update(
                label="wrong-label",
                excludes=["wrong-exclude"],
                now="wrong-clock",
                dry_run=not dry_run,
                cancel="wrong-event",
            )
            results = runner._run_instance(name, instance, now, cancel)
            assert len(results) == 1 and results[0].label == name and results[0].success
        for call in probe.calls:
            assert call["now"] == now and call["cancel"] is cancel
            assert call["dry_run"] is dry_run
            assert call["excludes"] == ["global-exclude", f"{call['label']}-exclude"]
        cancel.set()
        count = len(probe.calls)
        results = runner._run_instance("alpha", cfg.instances["alpha"], now, cancel)
        assert len(probe.calls) == count
        assert len(results) == 1 and results[0].label == "alpha" and not results[0].success
        assert results[0].archive is None and results[0].skipped is False

    def test_preflight_failures_precede_worker_results_and_skips_remain_skips(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy", "omega"))
        cfg = configure(monkeypatch, probe)
        probe.status = {"alpha-copy": "fail", "omega": "skip"}

        def outcomes(kwargs: dict[str, object]) -> Iterator[StepResult]:
            name = str(kwargs["label"])
            yield StepResult(name, True, f"outcome {name}", skipped=name == "omega")

        probe.behavior = outcomes
        results = list(Runner(cfg).run(list(cfg.instances.items())))
        assert results[0].label == "alpha-copy"
        assert results[0].success is False and results[0].message == "plan alpha-copy"
        assert not probe.started["alpha-copy"].is_set()
        assert {row.label for row in results} == {"alpha", "alpha-copy", "omega"}
        assert len(results) == 3
        omega = next(row for row in results if row.label == "omega")
        assert omega.success is True and omega.skipped is True
        assert {call["label"] for call in probe.plans} == set(cfg.instances)

    @pytest.mark.parametrize("message", ["preflight storage unavailable", "preflight permission denied"])
    def test_preflight_fatal_error_propagates_before_any_worker_starts(
        self, monkeypatch: pytest.MonkeyPatch, message: str
    ) -> None:
        class FatalProbe(CapabilityProbe):
            def plan(self, **kwargs: object) -> PlanEntry:
                raise FatalError(message)

        probe = FatalProbe(("alpha", "alpha-copy"))
        cfg = configure(monkeypatch, probe)
        with pytest.raises(FatalError, match=message):
            list(Runner(cfg).run(list(cfg.instances.items())))
        assert probe.calls == []

    def test_request_cancel_after_completion_and_successive_empty_run_reset_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy"))
        cfg = configure(monkeypatch, probe)
        probe.release_all()
        runner = Runner(cfg)
        assert runner.interrupted is False and runner.cancelled_names == ()
        runner.request_cancel()
        runner.request_cancel()
        assert runner.interrupted is True
        assert list(runner.run([])) == []
        assert runner.interrupted is False and runner.cancelled_names == ()
        first = list(runner.run(list(cfg.instances.items())))
        assert len(first) == 2 and all(row.success for row in first)
        first_event = probe.calls[0]["cancel"]
        runner.request_cancel()
        assert runner.interrupted is True
        second = list(runner.run(list(cfg.instances.items())))
        assert len(second) == 2 and all(row.success for row in second)
        assert runner.interrupted is False and runner.cancelled_names == ()
        assert probe.calls[-1]["cancel"] is not first_event
        assert not probe.calls[-1]["cancel"].is_set()

    def test_interrupt_preserves_completed_results_not_yet_collected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        probe = CapabilityProbe(("alpha", "alpha-copy"))
        cfg = configure(monkeypatch, probe)
        committed = threading.Event()

        def finish(kwargs: dict[str, object]) -> Iterator[StepResult]:
            name = str(kwargs["label"])
            if name == "alpha-copy":
                assert probe.release[name].wait(WAIT)
            yield StepResult(name, True, f"committed {name}")
            if name == "alpha-copy":
                committed.set()

        probe.behavior = finish
        runner = Runner(cfg, jobs=2)
        iterator = runner.run(list(cfg.instances.items()))
        try:
            first = next(iterator)
            assert first.label == "alpha"
            assert probe.started["alpha-copy"].wait(WAIT)
            probe.release["alpha-copy"].set()
            assert committed.wait(WAIT)
            runner.request_cancel()
            results = [first, *iterator]
        finally:
            probe.release_all()
            iterator.close()
        assert {row.label for row in results} == {"alpha", "alpha-copy"}
        assert len(results) == 2 and all(row.success for row in results)
        assert runner.interrupted is True and runner.cancelled_names == ()

    def test_interrupt_during_preflight_marks_every_unsubmitted_instance_cancelled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class InterruptedProbe(CapabilityProbe):
            def plan(self, **kwargs: object) -> PlanEntry:
                raise KeyboardInterrupt()

        probe = InterruptedProbe(("alpha-copy", "alpha"))
        cfg = configure(monkeypatch, probe)
        runner = Runner(cfg)
        results = list(runner.run(list(cfg.instances.items())))
        assert {row.label for row in results} == {"alpha", "alpha-copy"}
        assert len(results) == 2 and all(not row.success for row in results)
        assert runner.interrupted is True
        assert runner.cancelled_names == ("alpha", "alpha-copy")
        assert probe.calls == []
