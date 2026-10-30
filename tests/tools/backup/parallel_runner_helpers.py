from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from backup.capabilities import CAPABILITIES
from backup.config import BackupConfig
from backup.runner import Runner
from backup.step_result import PlanEntry, StepResult

WAIT = 5
NAMES = ("omega", "alpha-copy", "gamma", "alpha", "delta")
PRIORITY = ("alpha", "alpha-copy", "delta", "gamma", "omega")
ORDERS = {"alpha": 10, "alpha-copy": 10, "delta": 20, "gamma": 30, "omega": 40}


class CapabilityProbe:
    inputs: dict[str, object] = {"source": "", "out": "", "token": ""}

    def __init__(self, names: tuple[str, ...] = NAMES) -> None:
        self.started = {name: threading.Event() for name in names}
        self.release = {name: threading.Event() for name in names}
        self.calls: list[dict[str, Any]] = []
        self.plans: list[dict[str, Any]] = []
        self.thread_ids: list[int] = []
        self.lock = threading.Lock()
        self.active = 0
        self.maximum = 0
        self.status: dict[str, str] = {}
        self.behavior: Callable[[dict[str, Any]], Iterator[StepResult]] = self.blocked

    def plan(self, **kwargs: Any) -> PlanEntry:
        self.plans.append(dict(kwargs))
        name = kwargs["label"]
        return PlanEntry(name, kwargs["source"], kwargs["out"], self.status.get(name, "run"), f"plan {name}", False)

    def run(self, **kwargs: Any) -> Iterator[StepResult]:
        name = kwargs["label"]
        with self.lock:
            self.calls.append(kwargs)
            self.thread_ids.append(threading.get_ident())
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        self.started[name].set()
        try:
            yield from self.behavior(kwargs)
        finally:
            with self.lock:
                self.active -= 1

    def blocked(self, kwargs: dict[str, Any]) -> Iterator[StepResult]:
        name = kwargs["label"]
        assert self.release[name].wait(WAIT), f"worker {name} was not released"
        yield StepResult(name, True, f"complete {name}")

    def release_all(self) -> None:
        for event in self.release.values():
            event.set()


def configure(monkeypatch: pytest.MonkeyPatch, probe: CapabilityProbe) -> BackupConfig:
    monkeypatch.setitem(CAPABILITIES, "parallel-probe", probe)
    instances = {
        name: {
            "use": "parallel-probe",
            "order": ORDERS.get(name, 100),
            "exclude_add": [f"{name}-exclude"],
            "with": {"source": f"/source/{name}", "out": f"/output/{name}.tgz", "token": f"token-{name}"},
        }
        for name in probe.started
    }
    return BackupConfig.model_validate({"instances": instances, "excludes": ["global-exclude"]})


class Consumption:
    def __init__(self, runner: Runner, cfg: BackupConfig, probe: CapabilityProbe) -> None:
        self.runner, self.cfg, self.probe = runner, cfg, probe
        self.results: list[StepResult] = []
        self.errors: list[BaseException] = []
        self.received = {name: threading.Event() for name in probe.started}
        self.thread_ids: list[int] = []
        self.thread = threading.Thread(target=self.collect, daemon=True)

    def collect(self) -> None:
        try:
            for result in self.runner.run(list(self.cfg.instances.items())):
                self.results.append(result)
                self.thread_ids.append(threading.get_ident())
                self.received[result.label].set()
        except BaseException as exc:
            self.errors.append(exc)

    def __enter__(self) -> Consumption:
        self.thread.start()
        return self

    def finish(self) -> None:
        self.thread.join(WAIT)
        assert not self.thread.is_alive(), "runner did not finish bounded cleanup"
        assert self.errors == []

    def __exit__(self, *args: object) -> None:
        self.probe.release_all()
        self.thread.join(WAIT)
        assert not self.thread.is_alive(), "runner leaked its consumer or worker threads"
