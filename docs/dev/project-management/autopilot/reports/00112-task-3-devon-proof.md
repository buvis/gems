# Devon 3 exact adversarial proof

Logical persona: opus. Actual backend/model: OpenAI gpt-6.1-sol/high.

Scope: only the provided progress tests and public types; no PRD, acceptance, architecture, or test edits.

Original Runner SHA-256: `fe039619ab7cfd923fd76086dc3723340c7e31159b124c964cbbaa1728321a61`.

Command for every independent mutant: `uv run pytest tests/tools/backup/test_progress.py -k "runner or calling_thread or drain" -q --tb=line`. Timeout: 300 seconds.

## Experiment 1: Hard limit of two workers ignores jobs

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                **instance.with_,
                "label": name,
                "excludes": list(effective_excludes(self._cfg, instance)),
                "dry_run": self._dry_run,
                "now": now,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=2)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.364 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.98s
```

Weak point: TestRunnerCallingThread - ignores the jobs limit and caps all concurrency at two - use jobs=1 with two producers and assert only one starts before release; also verify jobs=3 admits three

Original bytes restored: yes.

## Experiment 2: Runtime timestamp is always None

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                **instance.with_,
                "label": name,
                "excludes": list(effective_excludes(self._cfg, instance)),
                "dry_run": self._dry_run,
                "now": None,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=self._jobs)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.255 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.95s
```

Weak point: TestRunnerCallingThread - passes now=None to every running capability - assert runtime now is a datetime and shared by all calls

Original bytes restored: yes.

## Experiment 3: Drops all capability input values

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                "label": name,
                "excludes": list(effective_excludes(self._cfg, instance)),
                "dry_run": self._dry_run,
                "now": now,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=self._jobs)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.267 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.96s
```

Weak point: TestRunnerCallingThread - omits every instance.with_ value from capability.run - configure a unique capability input and assert the exact forwarded value

Original bytes restored: yes.

## Experiment 4: Ignores instance-specific exclusion changes

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                **instance.with_,
                "label": name,
                "excludes": list(self._cfg.excludes),
                "dry_run": self._dry_run,
                "now": now,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=self._jobs)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.271 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.96s
```

Weak point: TestRunnerCallingThread - ignores inherit_excludes, exclude_add, and exclude_remove - configure per-instance exclusion changes and assert their resolved excludes

Original bytes restored: yes.

## Experiment 5: Turns cancellation results into success

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                **instance.with_,
                "label": name,
                "excludes": list(effective_excludes(self._cfg, instance)),
                "dry_run": self._dry_run,
                "now": now,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=self._jobs)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                if cancel.is_set():
                    rows = [StepResult(result.label, True, "backup completed successfully") for result in rows]
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.270 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.96s
```

Weak point: TestRunnerCancellation.test_runner_drains_queued_prefix_when_observer_requests_cancel_or_interrupts - reports cancelled writes as successful - assert success is False and the cancellation message is preserved

Original bytes restored: yes.

## Experiment 6: Silently truncates multi-result capabilities

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                **instance.with_,
                "label": name,
                "excludes": list(effective_excludes(self._cfg, instance)),
                "dry_run": self._dry_run,
                "now": now,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows[:1]
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=self._jobs)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.228 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.95s
```

Weak point: TestRunnerCallingThread - discards every StepResult after the first from a capability - yield multiple results from one capability and assert all results survive

Original bytes restored: yes.

## Experiment 7: Permanently freezes elapsed ticks after second callback

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                **instance.with_,
                "label": name,
                "excludes": list(effective_excludes(self._cfg, instance)),
                "dry_run": self._dry_run,
                "now": now,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=self._jobs)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run and tick_count < 2:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.234 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.94s
```

Weak point: TestRunnerCallingThread.test_runner_ticks_without_events_and_isolates_each_observer_exception - stops all ticks after exactly two callbacks - keep the capability blocked until a third tick and assert it arrives

Original bytes restored: yes.

## Experiment 8: Drops all progress after event 257 per label

Wrong implementation (entire replacement Runner):

```python
from __future__ import annotations

import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

__all__ = ["Runner"]


class Runner:
    def __init__(self, cfg: Any, *, dry_run: bool = False, jobs: int = 3,
                 on_progress: Any = None, on_tick: Any = None) -> None:
        self._cfg = cfg
        self._dry_run = dry_run
        self._jobs = jobs
        self._on_progress = on_progress
        self._on_tick = on_tick
        self._cancel = None
        self.interrupted = False
        self.cancelled_names = ()

    def request_cancel(self) -> None:
        self.interrupted = True
        if self._cancel is not None:
            self._cancel.set()

    def plan(self, selected: Any) -> list[PlanEntry]:
        now = datetime.now()
        return [CAPABILITIES[instance.use].plan(**instance.with_, label=name,
                excludes=list(effective_excludes(self._cfg, instance)), now=now)
                for name, instance in selected]

    def run(self, selected: Any) -> Any:
        self.interrupted = False
        cancel = threading.Event()
        self._cancel = cancel
        events = queue.Queue(maxsize=256)
        completed = queue.Queue()
        tick_count = 0
        counts = {}
        now = datetime.now()

        def enqueue(event: Any) -> None:
            counts[event.label] = counts.get(event.label, 0) + 1
            if counts[event.label] > 257:
                return
            while not cancel.is_set():
                try:
                    events.put(event, timeout=0.05)
                    return
                except queue.Full:
                    continue

        def observe(event: Any) -> None:
            if self._on_progress is not None:
                try:
                    self._on_progress(event)
                except KeyboardInterrupt:
                    self.request_cancel()
                except Exception:
                    pass

        def drain() -> None:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    return
                observe(event)

        def worker(name: str, instance: Any) -> list[StepResult]:
            capability = CAPABILITIES.get(instance.use)
            if capability is None:
                return [StepResult(name, False, "unknown capability")]
            call_kwargs = {
                **instance.with_,
                "label": name,
                "excludes": list(effective_excludes(self._cfg, instance)),
                "dry_run": self._dry_run,
                "now": now,
                "cancel": cancel,
                "progress": enqueue if self._on_progress is not None and not self._dry_run else None,
            }
            try:
                rows = list(capability.run(**call_kwargs))
                return rows
            except Exception as exc:
                return [StepResult(name, False, str(exc))]

        executor = ThreadPoolExecutor(max_workers=self._jobs)
        try:
            pending = set()
            for name, instance in selected:
                future = executor.submit(worker, name, instance)
                pending.add(future)
                future.add_done_callback(completed.put)
            while pending:
                drain()
                try:
                    future = completed.get_nowait()
                except queue.Empty:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        if self._on_tick is not None and not self._dry_run:
                            tick_count += 1
                            try:
                                self._on_tick()
                            except KeyboardInterrupt:
                                self.request_cancel()
                            except Exception:
                                pass
                    else:
                        observe(event)
                    continue
                pending.remove(future)
                drain()
                rows = future.result()
                for result in rows:
                    yield result
        finally:
            cancel.set()
            executor.shutdown(wait=True, cancel_futures=True)
            self._cancel = None
```

Exact measured output (return code 0; wall time 4.254 seconds):

```text
................                                                         [100%]
16 passed, 68 deselected in 3.93s
```

Weak point: TestRunnerBoundedQueue.test_runner_drains_full_queue_without_waiting_for_a_completed_future - silently discards event 258 and every later event - emit at least 258 events and assert their complete FIFO sequence

Original bytes restored: yes.

## Final restoration

Runner restored byte-for-byte: True. SHA-256: `fe039619ab7cfd923fd76086dc3723340c7e31159b124c964cbbaa1728321a61`. CHANGELOG.md was never modified.

Proven passing independent mutants: 8. Failed exploits: 0. No test reruns after this proof report.
