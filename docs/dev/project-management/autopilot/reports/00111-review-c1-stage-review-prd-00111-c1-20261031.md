---
catchup: skip
design: run
default_model: opus
model_tier_rationale: concurrency, cancellation and subprocess lifecycle decide correctness
---

# backup: bounded parallel jobs with clean cancellation

Source: `docs/dev/project-management/intake/processed/00107-backup-multi-source-parallel/discovery.md` (Q7, Q10, Q11). Depends on PRD 00110 (duplicate-output rejection, run-wide `now`). PRD 00112 depends on this one.

## Overview

### Problem Statement
`Runner.run` loops over instances one after another (`src/tools/backup/runner.py:31`). A run of many large trees takes the sum of all archive times. The system-tar writer blocks in `subprocess.run` (`src/tools/backup/capabilities/tar_archive.py:340`), so a Ctrl-C cannot stop the child cleanly, and nothing cancels a writer that is mid-archive.

### Target Users
The solo operator who runs many instances unattended and sometimes interrupts a run.

### Success Metrics
- `uv run pytest tests/tools/backup/test_parallel_runner.py -q` passes.
- `test_never_exceeds_jobs` proves at most `jobs` writers are active at once with five ready instances and default `jobs=3`.
- `test_cancel_cleans_temp_files_both_engines` passes: after cancellation no `*.tmp` sibling and no new final archive remain, and a prior output is unchanged.

## Functional Decomposition

### Capability: Bounded concurrency
Run up to N instances at once.

#### Feature: `--jobs`
- **Description**: CLI option and `Runner` parameter for the worker count.
- **Inputs**: `--jobs N` (a plain `int` option, default 3; the callback rejects a value below 1 with `console.failure("--jobs must be at least 1")` followed by `raise SystemExit(1)`, never a Click parse-time validator, per the AGENTS.md Click validation rule); `Runner(cfg, dry_run=..., jobs=N)`.
- **Outputs**: instances run on a `concurrent.futures.ThreadPoolExecutor(max_workers=jobs)` in `(order, name)` submit order; `--jobs 1` is sequential.
- **Behavior**: order is launch priority only, not a completion barrier. Results are yielded to the caller in completion order, from the calling thread only; workers never write to the console. A worker exception becomes a failed `StepResult` for that instance and does not stop the others. Instances rejected by PRD 00110's duplicate check are never submitted.

### Capability: Cancellation
Stop everything cleanly on interrupt.

#### Feature: Cooperative cancel signal
- **Description**: A `threading.Event` named `cancel` is passed to every capability call as the kwarg `cancel`.
- **Inputs**: `cancel: threading.Event`.
- **Outputs**: raising `ArchiveCancelled` (new exception in `src/tools/backup/capabilities/tar_archive.py`) from the Python writer, checked before each member is added, after which the existing `except BaseException` cleanup removes the temp file.
- **Behavior**: the system-tar writer starts tar with `subprocess.Popen` and waits with a loop of `process.communicate(timeout=0.2)` retries, passing `input=` on the first call only (a later call with `input` raises `ValueError`), checking `cancel` between retries; on cancel it calls `process.terminate()`, then `process.kill()` if it has not exited after 5 seconds, waits, removes the temp file, and raises `ArchiveCancelled`. `ArchiveCancelled` is not turned into a fallback to the Python engine.

#### Feature: Interrupt handling
- **Description**: Ctrl-C in the CLI stops the run.
- **Inputs**: `KeyboardInterrupt` in the calling thread while waiting for results.
- **Outputs**: `cancel` set; no new instance starts (`executor.shutdown(wait=True, cancel_futures=True)`); every still-active writer cleans up; completed archives and prior outputs are untouched; the CLI prints `console.failure("interrupted: ...")` naming the instances that did not finish, and exits 130 via `raise SystemExit(130)`, the pattern `src/tools/backup/cli.py` already uses for its nonzero exits.
- **Behavior**: an interrupted instance yields `StepResult(name, success=False, message="cancelled")`. `Runner.run` re-raises nothing; it ends after yielding the cancelled results and exposes `Runner.interrupted: bool` so the CLI can pick exit 130.

## Structural Decomposition

### Repository Structure

```
src/tools/backup/capabilities/tar_archive.py   # Maps to: Cooperative cancel signal
src/tools/backup/runner.py                     # Maps to: --jobs, Interrupt handling
src/tools/backup/cli.py                        # Maps to: --jobs, Interrupt handling
tests/tools/backup/test_parallel_runner.py     # Maps to: all features
tests/tools/backup/test_invariants.py          # Maps to: invariant guard (read only unless it fails)
docs/source/tools/backup.rst                   # Maps to: documentation
CHANGELOG.md                                   # Maps to: documentation
```

### Module: tar_archive
- **Maps to capability**: Cancellation
- **Responsibility**: observe `cancel`, stop both engines cleanly.
- **Location**: `src/tools/backup/capabilities/tar_archive.py`
- **Exports**: `ArchiveCancelled`
- New symbols: `ArchiveCancelled`, `cancel`, `jobs`, `interrupted`, `test_never_exceeds_jobs`, `test_cancel_cleans_temp_files_both_engines`

### Module: runner
- **Maps to capability**: Bounded concurrency, Cancellation
- **Responsibility**: pool, completion-order results, cancel on interrupt.
- **Location**: `src/tools/backup/runner.py`
- **Exports**: `Runner(cfg, dry_run=False, jobs=3)`, `Runner.interrupted`.

### Module: cli
- **Maps to capability**: Bounded concurrency, Cancellation
- **Responsibility**: `--jobs`, exit 130 on interrupt.
- **Location**: `src/tools/backup/cli.py`

## Dependency Graph

### Foundation Layer (Phase 0)
- **tar_archive**: no dependencies; built first.

### Core Layer (Phase 1)
- **runner**: Depends on [tar_archive]

### Integration Layer (Phase 2)
- **cli**: Depends on [runner]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Both writers can be cancelled.

**Tasks**:
- [ ] Add `ArchiveCancelled`, the `cancel` kwarg, the per-member check in `_write_archive`, and the Popen/poll/terminate/kill loop in `_write_archive_system_tar` (no deps) - Acceptance: `uv run pytest tests/tools/backup/test_parallel_runner.py -k "cancel_cleans or terminates_tar" -q` passes; the system-tar test uses a stub `tar` script on `PATH` that sleeps.

**Exit Criteria**: setting the event during a write leaves no temp file and no new final archive.

### Phase 1: Core
**Goal**: The runner runs bounded and cancels.

**Tasks**:
- [ ] Replace the sequential loop in `src/tools/backup/runner.py` by the pool described above, with `jobs`, completion-order yielding, `cancel`, and `interrupted` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_parallel_runner.py -k "jobs or order or failure_isolated or interrupt" -q` passes.

**Exit Criteria**: five instances with `jobs=3` never run more than three at once; one failing instance does not stop the others.

### Phase 2: Integration
**Goal**: CLI exposes it and it is documented.

**Tasks**:
- [ ] Add `--jobs` and the exit-130 path to `src/tools/backup/cli.py` (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/backup/test_parallel_runner.py -k cli -q` passes, including `--jobs 0` exiting 1 with `--jobs must be at least 1` in the console output.
- [ ] Document `--jobs`, ordering and Ctrl-C behaviour in `docs/source/tools/backup.rst`; add an `Added` line under `[Unreleased]` in `CHANGELOG.md` (depends on: Phase 1) - Acceptance: `rg -c "\-\-jobs" docs/source/tools/backup.rst CHANGELOG.md` prints a count of at least 1 for each file.

**Exit Criteria**: `uv run pytest tests/tools/backup -q` passes (including `tests/tools/backup/test_invariants.py`: no `print(`, `sys.exit`, `console.panic` in library files); `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: five instances, `jobs=3` (instrumented fake capability counting concurrency) → Expected: peak concurrency 3, all five results, launch order by `(order, name)`.
- **Edge case**: `jobs=1` → Expected: strictly sequential in `(order, name)` order.
- **Edge case**: a later instance finishes before an earlier one → Expected: it is yielded first.
- **Error case**: one instance raises → Expected: failed step for it, the rest succeed, overall exit 1.
- **Error case**: interrupt with two active and two queued → Expected: queued never start, active ones clean up, completed results kept, exit 130.
- **Error case**: interrupt during a system-tar archive that would replace an existing output → Expected: previous output bytes unchanged.

## Risks

- **Disk contention**: three writers on one disk may be slower. Mitigation: `--jobs 1`; no speed-up is promised.
- **Orphan child or temp file**: a killed Python or tar process leaves a temp file. Mitigation: terminate then kill with a bounded wait; temp cleanup in `finally`; tested for both engines.
- **Thread-safety of shared state**: workers must not mutate shared objects. Mitigation: each call gets its own kwargs; only the calling thread renders.

## Design Doc

# backup: bounded parallel jobs with clean cancellation — design

## Architecture fit

Keep execution in `backup.runner.Runner`, archive ownership in `backup.capabilities.tar_archive`, and rendering/exit codes in `backup.cli`. The shared runner remains usable by every interface without Click, console calls, or signal handlers in workers. Use the standard library only.

The root `AGENTS.md`, global instructions, PRD 00111, and project capsule were read. No nested `AGENTS.md`, applicable atlas, or `agent_docs/` was found. The capsule's active-work snapshot predates this batch; the checked-in code is authoritative for available seams.

PRD 00110 is parked, but its code remains: `Runner._plan`, `PlanEntry`, `TarArchive.plan`, and run-wide `now` already exist. Preserve preflight duplicate-output rejection before starting any worker and pass the same timestamp to every archive. There is no missing implementation dependency. Existing PRD 00110 review findings remain separately owned; the Python 3.14 test-injection problem is a conditional verification limitation, not evidence that these runtime seams are absent.

## Module placement

| Path | Change |
|---|---|
| `src/tools/backup/capabilities/tar_archive.py` | Edit: export `ArchiveCancelled`, propagate runtime cancellation, add writer checks, replace blocking `subprocess.run` with managed `Popen`. |
| `src/tools/backup/runner.py` | Edit: `jobs`, bounded executor scheduling, completion notification queue, shared event, interruption state, worker exception conversion. |
| `src/tools/backup/cli.py` | Edit: plain integer `--jobs`, callback validation, runner argument, interrupted summary and exit 130. |
| `tests/tools/backup/test_parallel_runner.py` | New: concurrency, ordering, interruption, both writer lifecycles, CLI integration. |
| `tests/tools/backup/test_backup_phase2.py` | Edit existing failing-tar fallback mock from `subprocess.run` to the new `Popen` seam. |
| `tests/tools/backup/test_plan_runner.py` | Edit execution-time `FatalError` expectation to the PRD's isolated worker failure contract; preserve preflight fatal-error expectations. |
| `docs/source/tools/backup.rst`, `README.md` | Edit: document jobs/default, completion ordering, interruption, and sequential escape hatch. README coverage follows the capsule's CLI documentation invariant. |
| `CHANGELOG.md` | Edit: one Added entry under Unreleased mentioning `--jobs` and cancellation. |

Keep `StepResult`, `PlanEntry`, `BackupConfig`, and the `Capability` protocol signatures unchanged. Runtime `cancel` belongs in capability kwargs, not configurable `inputs` or YAML. No framework, shared executor service, or cross-tool import is introduced. `tests/tools/backup/test_invariants.py` stays unchanged unless verification exposes an actual violation.

## Interfaces & contracts

### Archive cancellation

```python
class ArchiveCancelled(Exception):
    """Archive creation stopped before publication."""

__all__ = ["ArchiveCancelled", "TarArchive", "WalkResult"]

def _write_archive(
    out: Path, arcbase: Path, files: Iterable[Path], *, cancel: threading.Event | None = None
) -> None: ...

def _write_archive_system_tar(
    out: Path, arcbase: Path, files: Iterable[Path], *, cancel: threading.Event | None = None
) -> str | None: ...

# TarArchive static helper, with the existing result shape:
def _archive_result(
    label: str, arcbase: Path, out: Path, walk: WalkResult, engine: str,
    *, cancel: threading.Event | None = None,
) -> StepResult: ...
```

`ArchiveCancelled` is the PRD-required exception at the archive/runner boundary. It carries no new state. It must escape both writer helpers and the capability without triggering fallback. The runner converts it to exactly `StepResult(name, success=False, message="cancelled")`, with `archive=None` and `skipped=False`.

`TarArchive.run(self, **kwargs: object) -> Iterator[StepResult]` accepts an optional runtime `cancel` kwarg holding `threading.Event`. Omitting it preserves direct-call behavior. `_run_validated` forwards it to `_archive_result`; the latter passes the same event to both the selected engine and any legitimate Python fallback. Check a supplied event before selection starts, after selection, and before creating archive output. An already-cancelled call must not walk or write. No `cancel` entry is added to `TarArchive.inputs`.

The Python writer checks `cancel.is_set()` before every `tar.add`, after the member loop, and immediately before `os.replace`. A set event raises `ArchiveCancelled`. Keep the existing `except BaseException` temp cleanup, streaming compression, `fsync`, mode `0o600`, and atomic replacement. Cancellation during a single large member takes effect when that `tar.add` returns; v1 does not interrupt a file halfway through its copy. A final event check also covers an empty member iterable.

The system writer preserves the exact argv, NUL-delimited bytes input, `COPYFILE_DISABLE=1`, return-reason fallback behavior, permissions, and atomic publication. Start with `subprocess.Popen(..., stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, start_new_session=True)`. A private session prevents terminal Ctrl-C from killing tar independently of the runner's cancellation decision; this child needs no terminal input.

Call `process.communicate(input=filelist, timeout=0.2)` once. After `subprocess.TimeoutExpired`, retry `process.communicate(timeout=0.2)` without `input`. Check the event before spawn, between retries, after communicate succeeds, and immediately before publication. A timeout is a polling interval, not a failed archive or a fallback reason.

On cancellation while the child is alive: call `process.terminate()`, drain/reap with `process.communicate(timeout=5.0)`, then on `TimeoutExpired` call `process.kill()` and `process.communicate()` to reap it. Suppress only an already-exited-child race when signaling. Close owned pipes and remove the temp in cleanup. Any other exception after spawn must also stop/reap the live child before propagating or returning the existing invocation-failure fallback reason. Cancellation remains `ArchiveCancelled`, including cancellation during cleanup; it must not become a Python fallback. A child already exited still requires the event check before publication.

Publication is the existing `os.replace` operation. An archive published before cancellation is completed and is preserved. An observed cancellation before publication prevents replacement; the old output stays byte-identical, and a previously absent output stays absent. The immediately preceding check is cooperative, not a transactional synchronization primitive with arbitrary external event setters.

### Runner

```python
class Runner:
    interrupted: bool
    cancelled_names: tuple[str, ...]

    def __init__(
        self, cfg: BackupConfig, *, dry_run: bool = False, jobs: int = 3
    ) -> None: ...

    def run(self, selected: list[tuple[str, BackupInstance]]) -> Iterator[StepResult]: ...
    def plan(self, selected: list[tuple[str, BackupInstance]]) -> list[PlanEntry]: ...
    def request_cancel(self) -> None: ...

    def _run_instance(
        self, name: str, instance: BackupInstance, now: datetime, cancel: threading.Event
    ) -> list[StepResult]: ...
```

Reject `jobs < 1` in the constructor with `ValueError("jobs must be at least 1")` for non-CLI callers. Initialize `interrupted=False`, `cancelled_names=()`; reset them when a new `run` begins. One Runner supports successive runs, not concurrent calls to `run` on the same object.

`request_cancel()` is a calling-thread, idempotent consumer cancellation API. It sets `interrupted=True` and the active run event, if present. Store the current event in `self._cancel: threading.Event | None`; assign it when run iteration starts and clear it only after cleanup finishes. Calling `request_cancel()` after iteration has ended still sets `interrupted=True`, covering an interrupt while rendering the final summary. A new run resets the state as specified above. The method performs no rendering, yielding, joining, or exception raising. Both the runner's own KeyboardInterrupt handler and a consumer whose rendering was interrupted use this method.

Each run creates its own event named `cancel = threading.Event()`, completion queue `queue.Queue[Future[list[StepResult]]]`, and `ThreadPoolExecutor(max_workers=self._jobs)`. No executor is needed for an empty selection or a selection containing only preflight failures. Preserve `_plan(selected, now)` as the preflight step, before any submission; preflight `FatalError` retains its existing propagation contract. Preflight failure rows yield their existing failed results from the calling thread and are never submitted. Do not turn a preflight `skip` into a new failure; retain the capability's existing skip behavior.

Sort execution candidates by `(instance.order, name)` and submit in that order. Maintain at most `jobs` submitted, uncollected futures, and refill from the remaining candidates after each completion. This keeps the scheduling queue bounded and leaves not-yet-started instances under calling-thread ownership. With `jobs=1`, capability execution is strictly sequential. With larger values, ordering is submit priority; worker-start and completion order can differ.

`_run_instance` checks `cancel` before invoking the capability and builds a fresh kwargs dictionary with fresh excludes. Pass `label`, `excludes`, `dry_run`, `now`, and `cancel` after `instance.with_`, so runtime values win. Fully consume the capability iterator inside the worker and return its results as a list. Workers never yield to the outside caller or render output. Registered capabilities are shared, stateless objects; per-call mutation belongs in local variables.

Catch `ArchiveCancelled` first for the exact cancelled result. Catch other `Exception`, including execution-time `FatalError`, as a failed result with the existing `f"{name} failed: {exc}"` message; another instance must continue. This follows PRD 00111's worker-exception requirement and deliberately supersedes the older execution-time fatal-propagation test. Do not change preflight or config fatal-error handling. Do not swallow `BaseException` indiscriminately.

Register a future callback that only puts its future into the completion queue. The calling thread consumes that queue and yields the completed instance's result list. Queue notification order defines completion order; simultaneous completions have no required tie order. Results within one instance retain capability order. Preflight failures are immediately available and are emitted before worker results.

Catch calling-thread `KeyboardInterrupt` around preflight/scheduling/result collection and call `request_cancel()` before waiting for cleanup. Also check the event whenever iteration resumes after a yield and before every refill; consumer cancellation must enter the same shutdown/drain path even when no exception was thrown inside the generator. Stop submitting new futures and call `executor.shutdown(wait=True, cancel_futures=True)` when an executor exists. A worker entry check prevents queued wrappers from invoking a capability after cancellation. Preserve already-completed future results even if they were not yet rendered; never rewrite a committed success as cancelled merely because the main thread noticed it later. Active workers observe the event and return their cleanup outcome. Every unsubmitted/cancelled-future instance gets one cancelled result. No instance gets a second terminal result.

Populate `cancelled_names` from the names receiving cancelled results, in `(order, name)` order. This small interface lets the CLI name unfinished instances without parsing message text. After draining completed and cancelled outcomes, `run` ends normally; it re-raises no handled `KeyboardInterrupt`. Exit 130 takes priority even when all work happened to finish at the interruption boundary and the names tuple is empty. In `finally`, generator abandonment or an unexpected calling-thread exception sets `cancel` and joins the executor before leaving, so early consumer exit cannot leak active writers. No output occurs during cleanup.

### CLI

```python
@click.option("--jobs", type=int, default=3, show_default=True,
              help="Run at most this many archive instances at once.")

def _report_steps(
    steps: Iterable[StepResult], *, dry_run: bool = False,
    on_interrupt: Callable[[], None] | None = None,
) -> bool: ...

def _run_plan(
    cfg: BackupConfig, plan: list[tuple[str, BackupInstance]], *,
    dry_run: bool, plan_only: bool, jobs: int = 3,
) -> bool: ...
```

Add `jobs: int` to the Click callback. Before config loading or other early-return modes, reject `jobs < 1` with exactly `console.failure("--jobs must be at least 1")` and `raise SystemExit(1)`. Do not use `IntRange` or a parse-time custom validator. Keep existing flag conflict validation and selectors.

Instantiate `Runner(cfg, dry_run=dry_run, jobs=jobs)`. Keep `--plan` read-only; it does not construct an executor or invoke writers. Real and dry-run execution use the same scheduling path. Keep the concrete generator in a local `steps = runner.run(plan)` and call `_report_steps(steps, dry_run=dry_run, on_interrupt=runner.request_cancel)`. The CLI owns interruptions in consumer code, including `_report_step`, counter rendering, and final summary rendering: a suspended generator cannot catch those exceptions.

With `on_interrupt` supplied, `_report_steps` catches `KeyboardInterrupt` around consuming and rendering each step and its summary, calls `on_interrupt()`, and resumes consumption of the same iterator until exhaustion. Keep any fetched-but-not-fully-rendered step pending and retry its render; count each step once. Keep the counters across retries. An interrupt must not discard the generator, invoke `close()` as the cancellation path, or restart a run. Resuming it lets the runner observe the event, stop refill, join active writers, and yield cancelled outcomes. Already-completed/published outcomes stay successful even if their rendering was interrupted. Repeated interrupts repeat the idempotent cancellation request and continue draining. If no callback is supplied, preserve the helper's existing KeyboardInterrupt propagation behavior. Use `finally` in `_run_plan` to close the retained generator on an unrelated consumer exception, invoking the runner's resource-cleanup guarantee.

After `_report_steps` finishes, if `runner.interrupted`, print `console.failure("interrupted: " + ", ".join(runner.cancelled_names))`; use `"interrupted: no unfinished instances"` when the tuple is empty. Catch KeyboardInterrupt during this final interruption message, request cancellation again, and retry the message before `raise SystemExit(130)`. An interrupt during the ordinary final summary also uses the callback above, so it reaches this exit-130 decision. Otherwise return the existing failure boolean and retain exit 1 for ordinary failures/unknown selectors, exit 0 for success. Workers have no access to the console.

## Data flow

1. CLI validates jobs and existing flag combinations, loads config, selects instances, and applies one-instance overrides.
2. Runner captures one `datetime.now()`, computes the complete duplicate-aware preflight, emits rejected rows, and submits the first bounded group.
3. Each worker consumes one capability iterator with isolated kwargs and the shared cancellation event. The capability selects members and invokes its writer; only atomic publication creates/replaces a final archive.
4. Future callbacks notify the completion queue. The calling thread collects finished results, replenishes scheduling capacity, and yields results to the CLI for rendering.
5. Ctrl-C while collecting results is handled by the runner; Ctrl-C during rendering is handled by the CLI through `Runner.request_cancel()` while retaining and draining the same iterator. The event stops replenishment, cancels pending work, joins writers, preserves committed successes, emits cancelled outcomes for unfinished instances, and ends iteration. The CLI renders the final interruption message and exits 130.

## Reuse inventory

Sweep used the host `rationalizations.md` synonym guidance: execution verbs `run/submit/start`, nouns `executor/pool/thread/jobs`; lifecycle verbs `cancel/interrupt/shutdown/terminate/kill/wait`, nouns `process/archive/temp`; persistence verbs `write/replace/atomic`; inspection verbs `plan/resolve/select` and output nouns. Searches used `rg` over backup, sysup, pybase, and their relevant tests. Known symbols `Runner`, `communicate`, `os.replace`, and `_plan` produced hits, verifying search operation.

- `src/tools/backup/runner.py:Runner._plan`: reuse the complete duplicate-output preflight and one run-wide timestamp; no worker may bypass rejection.
- `src/tools/backup/config.py:applicable_instances`, `effective_excludes`: reuse `(order, name)` semantics and exclude merging; copy kwargs/excludes per worker.
- `src/tools/backup/capabilities/tar_archive.py:_run_validated`, `_walk_tree`, `_select_items`: preserve selection, bundles, excludes, skip outcomes, and source-relative member names; thread cancellation through the existing entry point.
- `src/tools/backup/capabilities/tar_archive.py:_write_archive`, `_write_archive_system_tar`: extend existing streaming temp/fsync/replace ownership and cleanup instead of adding another archive implementation.
- `src/lib/buvis/pybase/filesystem/atomic_write.py`: existing archive writers already implement its streaming equivalent; do not buffer an archive into `atomic_write_bytes`.
- `src/tools/backup/cli.py:_report_step`, `_report_steps`, `_run_plan`: retain result rendering/counters and existing exit patterns; inspect runner interruption after iteration.
- `src/tools/backup/step_result.py:StepResult`, `ArchiveMeta`, `PlanEntry`: use current result records unchanged.
- `src/tools/sysup/runner.py:_run`: reference for child cleanup on `BaseException` and process isolation; do not import across tools. Its timeout policy and console-oriented runner are unsuitable as backup's execution engine.
- `tests/tools/backup/test_replace_after_complete.py`: reuse prior-output byte checks and publication-boundary assertions for cancelled writes.
- No reusable bounded backup executor or cooperative archive-cancellation helper found; greps tried `ThreadPoolExecutor|as_completed|FIRST_COMPLETED|cancel_futures|add_done_callback|Queue\[` and `cancel|interrupt|shutdown|terminate|kill|wait|pool|thread|complete|finish`. Sysup has related subprocess lifecycle code, but no same-contract helper and cross-tool imports are prohibited.

## Alternatives considered

1. **Smallest diff: submit every selected instance, then iterate `as_completed`.** Bounds active workers, but queues the entire selection and complicates preventing queued work after interruption. Futures completed before `as_completed` begins also have no preserved notification order.
2. **Chosen: bounded submissions plus completion notifications.** Adds one standard-library queue and a small refill loop. It bounds pending state, gives the calling thread control over new launches, and preserves observable completion order without a barrier between configured orders.
3. **Async subprocesses or process workers.** Larger architectural change, unnecessary serialization or a second execution path, and poor fit for existing synchronous Python archive capabilities. Threads preserve the shared capability seam.

Keep per-member cooperative cancellation rather than wrapping all file reads or introducing a generic cancellable stream. That smaller writer change meets v1; finer cancellation latency can extend it later.

## Risks & edge cases

- A cancellation check immediately before `os.replace` minimizes the publication boundary but cannot make an independently set event transactional with a filesystem rename. Tests place cancellation before that check and distinguish it from completed publication. Existing completed outputs must never be deleted during cleanup.
- Python cancellation waits for the current `tar.add`; selection and filesystem calls can also block before the post-selection check. No fixed end-to-end Python cancellation latency is promised.
- The specified terminate/kill sequence owns the direct tar child. Arbitrary descendant process supervision is outside v1; use a direct sleeping Python stub for lifecycle tests, rather than a shell that leaves a separate sleep child. Real tar/gzip behavior must remain covered by the real-engine smoke test.
- Repeated Ctrl-C during cleanup must not abandon child reaping or executor shutdown. Handle a further calling-thread interrupt by retaining the set event and continuing the join; do not introduce global signal handlers in library code.
- `CAPABILITIES` holds singleton objects. Current `TarArchive` has no mutable call state; a future capability with shared mutable fields must make them safe before concurrent registration. Config input containers are read-only during execution.
- PRD 00110 uses lexical normalized output identity. Symlink, case-folded, or relative/absolute aliases remain its documented limitation; do not silently broaden its settled collision contract here.
- PRD 00110's review recorded 30 pre-existing Python 3.14 failures because `test_plan_errors.py` patches `Path.stat`, which newer pathlib metadata methods bypass. The active environment is Python 3.13. Preserve ownership in held PRDs 00113/00114; if checking 3.14, report those failures separately from new test regressions. Do not claim all supported-runtime gates pass until that separate baseline is fixed.
- Likely next change: PRD 00112 progress/quiet. Keep completion rendering on the calling thread; a later progress queue can share that ownership without workers writing to console.
- Likely next change: finer cancellation while reading a large member or selecting a huge tree. The runtime event can extend to those loops without changing result fields or CLI contracts.
- Likely next change: per-run disk limits or additional capabilities. Bounded submissions are local to `Runner`; avoid exposing executor internals or adding jobs to YAML prematurely.

## Test strategy outline

Use events/barriers and locked counters, with bounded test-side waits and release in `finally`; avoid timing-based assertions for ordering. New tests live in `test_parallel_runner.py`, organized in classes and kept small with fixtures/helpers.

- `test_never_exceeds_jobs`: five ready instances and default jobs=3; hold the first group, assert exactly three active, release them, and assert every result and peak=3. Repeat jobs=1 for strictly sequential `(order, name)` execution.
- Submit-order test: spy on executor submissions and assert sorted priorities independently from nondeterministic thread starts. Completion-order test: keep earlier instances blocked, finish a later one, and verify it is yielded first from the calling thread. Check no capability runs during `plan` and duplicate failures never enter the executor.
- `test_failure_isolated`: ordinary worker exception and execution-time FatalError each become the named failed step while another instance succeeds. Keep preflight FatalError propagation tests unchanged. Verify run-wide now and independent kwargs/exclude lists through all workers.
- `test_interrupt`: inject one calling-thread KeyboardInterrupt at the completion-collection seam after two workers become active and two candidates remain unsubmitted. Assert event identity, zero later capability starts, preserved already-completed success, one cancellation outcome per unfinished instance, joined workers, no duplicate result, `interrupted=True`, and deterministic `cancelled_names`. Verify fresh runner state on a second run and cleanup on generator close.
- `test_cancel_cleans_temp_files_both_engines`: parameterize both engines and prior-output presence. Set the event during an actual temp write; assert ArchiveCancelled/cancelled result, no sibling `*.tmp`, no new final, and byte-identical prior output. Add post-last-member/pre-publication cancellation to catch a missing final check. Assert no Python fallback on system cancellation.
- `test_terminates_tar`: executable direct-process stub named tar on PATH sleeps and records its PID; cancel during communicate, then prove it was reaped and no artifact published. A controlled Popen fake covers multiple TimeoutExpired retries, input passed once, terminate, five-second grace, kill escalation, already-exited races, and exceptional cleanup without waiting five real seconds. Release/kill test processes in fixture teardown.
- Preserve existing real system-tar content parity, NUL/newline safety, fallback reason, archive mode, fsync, atomic replacement, bundles, excludes and skips. Adapt the existing fallback mock to Popen; do not replace behavioral coverage with mock-call-only tests.
- `test_cli_interrupt_during_render`: let one instance publish successfully while another writer remains active, inject a one-shot KeyboardInterrupt from `_report_step`, and assert the CLI requests cancellation, resumes/drains the same iterator, renders its pending success once after retry, preserves its published bytes, starts no further candidates, joins the other writer, removes its temp, names unfinished instances, and exits 130. Add an interrupt from the normal final summary with an already-exhausted iterator and assert exit 130 without rewriting any completed outcome.
- CLI tests cover default/explicit jobs forwarding, `--jobs 0` and negative values with the exact console message/exit 1, ordinary worker failure/exit 1, interruption names/exit 130, successful/empty run exit 0, and read-only plan/list modes.

Required scoped commands: `uv run pytest tests/tools/backup/test_parallel_runner.py -q`; its PRD `-k` subsets; `uv run pytest tests/tools/backup -q`; `uv run ruff check src/tools/backup tests/tools/backup`; `uv run mypy src/tools/backup`; and `rg -c "\-\-jobs" docs/source/tools/backup.rst CHANGELOG.md`. Confirm the runtime used, report known 00110 baseline failures separately, and run the project-required broader gate during implementation. Unresolved questions: none required before planning; direct-child ownership and cooperative cancellation latency are explicit v1 limits above.

## Review log

Dispatch 1 actual host identity: `gpt-6.1-sol/high`; the pinned workflow source token below remains `claude` as required by the design review protocol.

- Resolved blocker — `## Interfaces & contracts` / Runner and CLI previously left KeyboardInterrupt during `_report_step` or `_report_steps` outside the suspended runner generator's handler. Added idempotent `Runner.request_cancel()`, explicit CLI callback ownership, retained-iterator draining, pending-step/counter preservation, and interrupt-safe final exit-130 reporting. `## Test strategy outline` now requires render-time and final-summary interruption tests.
- Non-blocker (recorded, not fixed) — `## Interfaces & contracts` / Runner: `_run_instance` fully materializes a capability iterator; when a later ArchiveCancelled occurs, conversion can lose an earlier successful result prefix from a multi-result capability.
- Non-blocker (recorded, not fixed) — `## Interfaces & contracts` / Archive cancellation: stopping only the direct tar child can leave a compressor/descendant holding pipes; the final unbounded `communicate()` after terminate/kill can then hang.

Checked-correct notes, verbatim:

- Architecture fit / Module placement: Execution, archive ownership, and rendering remain in their existing layers.
- Runner: Bounded submitted futures, per-run state, isolated kwargs, and notification-based completion ordering form a coherent scheduling contract.
- Archive cancellation: Final cancellation checks, atomic replacement, and temp cleanup preserve prior output before publication.
- Runner / CLI: Preflight fatal errors remain distinct from isolated execution failures; invalid jobs use callback validation.
- Test strategy outline: Event-driven ordering tests and real writer checks provide meaningful coverage without timing-dependent assertions.

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 0

dispatch 2: codex unavailable, Claude fallback — host role swap: external Claude weekly quota exhausted, resets 2026-11-01 10:00 Europe/Prague; native fallback gpt-6.1-sol/high. Failed external output: autopilot/reports/00111-design-review-2.txt.
dispatch 2 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 3, question 0
- Non-blocker: Runner._run_instance can lose successful prefixes from a multi-result iterator on later cancellation/failure; no current multi-result publication path is established. Retained from dispatch1, not changed.
- Non-blocker: Archive cancellation direct-child signaling plus unbounded final communicate may wait on descendant-held pipes; retained v1 limitation, not changed.
- Non-blocker: Risks & edge cases requires repeated Ctrl-C cleanup, but Test strategy outline only explicitly verifies one-shot interruption. Additional second-interrupt cleanup tests are a future verification improvement.
- Checked correct: Architecture fit/Module placement separation; Runner bounded scheduling and completion notification; Archive cancellation atomic output preservation; CLI retained-iterator draining; Alternatives considered rationale.
Open cardinal sins/blockers: none. Weak dispatches: none.
