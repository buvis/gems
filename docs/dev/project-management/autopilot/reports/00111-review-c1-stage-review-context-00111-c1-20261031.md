# Review Context

## Completed Tasks

| ID | Task | Status | Commit | Description | Shared with |
|----|------|--------|--------|-------------|-------------|
| 1 | Cancellable archive writers | completed |  | Cancellable archive writers  Location: src/tools/backup/capabilities/tar_archive.py, CHANGELOG.md  Reuse: existing backup archive atomic writers, Runner._plan, _report_steps and current console/result conventions.  Contract (verbatim — reviewed design):  ### Archive cancellation  ```python class ArchiveCancelled(Exception):     """Archive creation stopped before publication."""  __all__ = ["ArchiveCancelled", "TarArchive", "WalkResult"]  def _write_archive(     out: Path, arcbase: Path, files: Iterable[Path], *, cancel: threading.Event \| None = None ) -> None: ...  def _write_archive_system_tar(     out: Path, arcbase: Path, files: Iterable[Path], *, cancel: threading.Event \| None = None ) -> str \| None: ...  # TarArchive static helper, with the existing result shape: def _archive_result(     label: str, arcbase: Path, out: Path, walk: WalkResult, engine: str,     *, cancel: threading.Event \| None = None, ) -> StepResult: ... ```  `ArchiveCancelled` is the PRD-required exception at the archive/runner boundary. It carries no new state. It must escape both writer helpers and the capability without triggering fallback. The runner converts it to exactly `StepResult(name, success=False, message="cancelled")`, with `archive=None` and `skipped=False`.  `TarArchive.run(self, **kwargs: object) -> Iterator[StepResult]` accepts an optional runtime `cancel` kwarg holding `threading.Event`. Omitting it preserves direct-call behavior. `_run_validated` forwards it to `_archive_result`; the latter passes the same event to both the selected engine and any legitimate Python fallback. Check a supplied event before selection starts, after selection, and before creating archive output. An already-cancelled call must not walk or write. No `cancel` entry is added to `TarArchive.inputs`.  The Python writer checks `cancel.is_set()` before every `tar.add`, after the member loop, and immediately before `os.replace`. A set event raises `ArchiveCancelled`. Keep the existing `except BaseException` temp cleanup, streaming compression, `fsync`, mode `0o600`, and atomic replacement. Cancellation during a single large member takes effect when that `tar.add` returns; v1 does not interrupt a file halfway through its copy. A final event check also covers an empty member iterable.  The system writer preserves the exact argv, NUL-delimited bytes input, `COPYFILE_DISABLE=1`, return-reason fallback behavior, permissions, and atomic publication. Start with `subprocess.Popen(..., stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, start_new_session=True)`. A private session prevents terminal Ctrl-C from killing tar independently of the runner's cancellation decision; this child needs no terminal input.  Call `process.communicate(input=filelist, timeout=0.2)` once. After `subprocess.TimeoutExpired`, retry `process.communicate(timeout=0.2)` without `input`. Check the event before spawn, between retries, after communicate succeeds, and immediately before publication. A timeout is a polling interval, not a failed archive or a fallback reason.  On cancellation while the child is alive: call `process.terminate()`, drain/reap with `process.communicate(timeout=5.0)`, then on `TimeoutExpired` call `process.kill()` and `process.communicate()` to reap it. Suppress only an already-exited-child race when signaling. Close owned pipes and remove the temp in cleanup. Any other exception after spawn must also stop/reap the live child before propagating or returning the existing invocation-failure fallback reason. Cancellation remains `ArchiveCancelled`, including cancellation during cleanup; it must not become a Python fallback. A child already exited still requires the event check before publication.  Publication is the existing `os.replace` operation. An archive published before cancellation is completed and is preserved. An observed cancellation before publication prevents replacement; the old output stays byte-identical, and a previously absent output stays absent. The immediately preceding check is cooperative, not a transactional synchronization primitive with arbitrary external event setters.    Details: - Implement only this feature slice. - Include its release note in CHANGELOG.md when listed; do not alter prior notes. - Tests belong to tests/tools/backup/test_parallel_runner.py, with sibling test modules if needed; required PRD-named tests and -k subsets remain in the named file.  Acceptance criteria: `uv run pytest tests/tools/backup/test_parallel_runner.py -k "cancel_cleans or terminates_tar" -q` passes; the system-tar test uses a stub `tar` script on `PATH` that sleeps.  Verify: uv run pytest tests/tools/backup/test_parallel_runner.py -k "cancel_cleans or terminates_tar" -q |  |
| 2 | Bounded parallel runner and interruption | completed |  | Bounded parallel runner and interruption  Location: src/tools/backup/runner.py, CHANGELOG.md  Reuse: existing backup archive atomic writers, Runner._plan, _report_steps and current console/result conventions.  Contract (verbatim — reviewed design): ### Runner  ```python class Runner:     interrupted: bool     cancelled_names: tuple[str, ...]      def __init__(         self, cfg: BackupConfig, *, dry_run: bool = False, jobs: int = 3     ) -> None: ...      def run(self, selected: list[tuple[str, BackupInstance]]) -> Iterator[StepResult]: ...     def plan(self, selected: list[tuple[str, BackupInstance]]) -> list[PlanEntry]: ...     def request_cancel(self) -> None: ...      def _run_instance(         self, name: str, instance: BackupInstance, now: datetime, cancel: threading.Event     ) -> list[StepResult]: ... ```  Reject `jobs < 1` in the constructor with `ValueError("jobs must be at least 1")` for non-CLI callers. Initialize `interrupted=False`, `cancelled_names=()`; reset them when a new `run` begins. One Runner supports successive runs, not concurrent calls to `run` on the same object.  `request_cancel()` is a calling-thread, idempotent consumer cancellation API. It sets `interrupted=True` and the active run event, if present. Store the current event in `self._cancel: threading.Event \| None`; assign it when run iteration starts and clear it only after cleanup finishes. Calling `request_cancel()` after iteration has ended still sets `interrupted=True`, covering an interrupt while rendering the final summary. A new run resets the state as specified above. The method performs no rendering, yielding, joining, or exception raising. Both the runner's own KeyboardInterrupt handler and a consumer whose rendering was interrupted use this method.  Each run creates its own event named `cancel = threading.Event()`, completion queue `queue.Queue[Future[list[StepResult]]]`, and `ThreadPoolExecutor(max_workers=self._jobs)`. No executor is needed for an empty selection or a selection containing only preflight failures. Preserve `_plan(selected, now)` as the preflight step, before any submission; preflight `FatalError` retains its existing propagation contract. Preflight failure rows yield their existing failed results from the calling thread and are never submitted. Do not turn a preflight `skip` into a new failure; retain the capability's existing skip behavior.  Sort execution candidates by `(instance.order, name)` and submit in that order. Maintain at most `jobs` submitted, uncollected futures, and refill from the remaining candidates after each completion. This keeps the scheduling queue bounded and leaves not-yet-started instances under calling-thread ownership. With `jobs=1`, capability execution is strictly sequential. With larger values, ordering is submit priority; worker-start and completion order can differ.  `_run_instance` checks `cancel` before invoking the capability and builds a fresh kwargs dictionary with fresh excludes. Pass `label`, `excludes`, `dry_run`, `now`, and `cancel` after `instance.with_`, so runtime values win. Fully consume the capability iterator inside the worker and return its results as a list. Workers never yield to the outside caller or render output. Registered capabilities are shared, stateless objects; per-call mutation belongs in local variables.  Catch `ArchiveCancelled` first for the exact cancelled result. Catch other `Exception`, including execution-time `FatalError`, as a failed result with the existing `f"{name} failed: {exc}"` message; another instance must continue. This follows PRD 00111's worker-exception requirement and deliberately supersedes the older execution-time fatal-propagation test. Do not change preflight or config fatal-error handling. Do not swallow `BaseException` indiscriminately.  Register a future callback that only puts its future into the completion queue. The calling thread consumes that queue and yields the completed instance's result list. Queue notification order defines completion order; simultaneous completions have no required tie order. Results within one instance retain capability order. Preflight failures are immediately available and are emitted before worker results.  Catch calling-thread `KeyboardInterrupt` around preflight/scheduling/result collection and call `request_cancel()` before waiting for cleanup. Also check the event whenever iteration resumes after a yield and before every refill; consumer cancellation must enter the same shutdown/drain path even when no exception was thrown inside the generator. Stop submitting new futures and call `executor.shutdown(wait=True, cancel_futures=True)` when an executor exists. A worker entry check prevents queued wrappers from invoking a capability after cancellation. Preserve already-completed future results even if they were not yet rendered; never rewrite a committed success as cancelled merely because the main thread noticed it later. Active workers observe the event and return their cleanup outcome. Every unsubmitted/cancelled-future instance gets one cancelled result. No instance gets a second terminal result.  Populate `cancelled_names` from the names receiving cancelled results, in `(order, name)` order. This small interface lets the CLI name unfinished instances without parsing message text. After draining completed and cancelled outcomes, `run` ends normally; it re-raises no handled `KeyboardInterrupt`. Exit 130 takes priority even when all work happened to finish at the interruption boundary and the names tuple is empty. In `finally`, generator abandonment or an unexpected calling-thread exception sets `cancel` and joins the executor before leaving, so early consumer exit cannot leak active writers. No output occurs during cleanup.    Details: - Implement only this feature slice. - Include its release note in CHANGELOG.md when listed; do not alter prior notes. - Tests belong to tests/tools/backup/test_parallel_runner.py, with sibling test modules if needed; required PRD-named tests and -k subsets remain in the named file.  Acceptance criteria: `uv run pytest tests/tools/backup/test_parallel_runner.py -k "jobs or order or failure_isolated or interrupt" -q` passes.  Verify: uv run pytest tests/tools/backup/test_parallel_runner.py -k "jobs or order or failure_isolated or interrupt" -q |  |
| 3 | CLI jobs and exit 130 | completed |  | CLI jobs and exit 130  Location: src/tools/backup/cli.py, CHANGELOG.md  Reuse: existing backup archive atomic writers, Runner._plan, _report_steps and current console/result conventions.  Contract (verbatim — reviewed design): ### CLI  ```python @click.option("--jobs", type=int, default=3, show_default=True,               help="Run at most this many archive instances at once.")  def _report_steps(     steps: Iterable[StepResult], *, dry_run: bool = False,     on_interrupt: Callable[[], None] \| None = None, ) -> bool: ...  def _run_plan(     cfg: BackupConfig, plan: list[tuple[str, BackupInstance]], *,     dry_run: bool, plan_only: bool, jobs: int = 3, ) -> bool: ... ```  Add `jobs: int` to the Click callback. Before config loading or other early-return modes, reject `jobs < 1` with exactly `console.failure("--jobs must be at least 1")` and `raise SystemExit(1)`. Do not use `IntRange` or a parse-time custom validator. Keep existing flag conflict validation and selectors.  Instantiate `Runner(cfg, dry_run=dry_run, jobs=jobs)`. Keep `--plan` read-only; it does not construct an executor or invoke writers. Real and dry-run execution use the same scheduling path. Keep the concrete generator in a local `steps = runner.run(plan)` and call `_report_steps(steps, dry_run=dry_run, on_interrupt=runner.request_cancel)`. The CLI owns interruptions in consumer code, including `_report_step`, counter rendering, and final summary rendering: a suspended generator cannot catch those exceptions.  With `on_interrupt` supplied, `_report_steps` catches `KeyboardInterrupt` around consuming and rendering each step and its summary, calls `on_interrupt()`, and resumes consumption of the same iterator until exhaustion. Keep any fetched-but-not-fully-rendered step pending and retry its render; count each step once. Keep the counters across retries. An interrupt must not discard the generator, invoke `close()` as the cancellation path, or restart a run. Resuming it lets the runner observe the event, stop refill, join active writers, and yield cancelled outcomes. Already-completed/published outcomes stay successful even if their rendering was interrupted. Repeated interrupts repeat the idempotent cancellation request and continue draining. If no callback is supplied, preserve the helper's existing KeyboardInterrupt propagation behavior. Use `finally` in `_run_plan` to close the retained generator on an unrelated consumer exception, invoking the runner's resource-cleanup guarantee.  After `_report_steps` finishes, if `runner.interrupted`, print `console.failure("interrupted: " + ", ".join(runner.cancelled_names))`; use `"interrupted: no unfinished instances"` when the tuple is empty. Catch KeyboardInterrupt during this final interruption message, request cancellation again, and retry the message before `raise SystemExit(130)`. An interrupt during the ordinary final summary also uses the callback above, so it reaches this exit-130 decision. Otherwise return the existing failure boolean and retain exit 1 for ordinary failures/unknown selectors, exit 0 for success. Workers have no access to the console.   Details: - Implement only this feature slice. - Include its release note in CHANGELOG.md when listed; do not alter prior notes. - Tests belong to tests/tools/backup/test_parallel_runner.py, with sibling test modules if needed; required PRD-named tests and -k subsets remain in the named file.  Acceptance criteria: `uv run pytest tests/tools/backup/test_parallel_runner.py -k cli -q` passes, including `--jobs 0` exiting 1 with `--jobs must be at least 1` in the console output.  Verify: uv run pytest tests/tools/backup/test_parallel_runner.py -k cli -q |  |
| 4 | Document parallel backup operation | completed |  | Document parallel backup operation  Location: docs/source/tools/backup.rst  Reuse: existing backup archive atomic writers, Runner._plan, _report_steps and current console/result conventions.  Contract (verbatim — PRD documentation slice): - [ ] Document `--jobs`, ordering and Ctrl-C behaviour in `docs/source/tools/backup.rst`; add an `Added` line under `[Unreleased]` in `CHANGELOG.md` (depends on: Phase 1)  Details: - Implement only this feature slice. - Include its release note in CHANGELOG.md when listed; do not alter prior notes. - Tests belong to tests/tools/backup/test_parallel_runner.py, with sibling test modules if needed; required PRD-named tests and -k subsets remain in the named file.  Acceptance criteria: `rg -c "\-\-jobs" docs/source/tools/backup.rst CHANGELOG.md` prints a count of at least 1 for each file.  Verify: rg -c "\-\-jobs" docs/source/tools/backup.rst CHANGELOG.md |  |
| 5 | Update backup README interface | completed |  | Update backup README interface  Location: README.md  Reuse: existing backup archive atomic writers, Runner._plan, _report_steps and current console/result conventions.  Contract (verbatim — PRD documentation slice): - [ ] Document `--jobs`, ordering and Ctrl-C behaviour in `docs/source/tools/backup.rst`; add an `Added` line under `[Unreleased]` in `CHANGELOG.md` (depends on: Phase 1)  Details: - Implement only this feature slice. - Include its release note in CHANGELOG.md when listed; do not alter prior notes. - Tests belong to tests/tools/backup/test_parallel_runner.py, with sibling test modules if needed; required PRD-named tests and -k subsets remain in the named file.  Acceptance criteria: `rg -c "\-\-jobs" docs/source/tools/backup.rst CHANGELOG.md` prints a count of at least 1 for each file.  Verify: rg -n -- --jobs README.md |  |

## Code Changes

### Changed Files
_Diff scope: incremental review (changes since 9a7f78c8eb0e4148181584f92eb649cfec590034)_

```
 CHANGELOG.md                                       |   3 +
 README.md                                          |   9 +
 .../autopilot/autocodex-metrics.jsonl              |   2 +
 .../a3e2a400dac044409603bd60651ac053.jsonl         | 377 +++++++++++
 .../a3e2a400dac044409603bd60651ac053.prompt.md     | 256 +++++++
 .../a3e2a400dac044409603bd60651ac053.stderr        |  11 +
 .../d32406e872ba4eaa916cb75e0f7be239.jsonl         | 685 +++++++++++++++++++
 .../d32406e872ba4eaa916cb75e0f7be239.prompt.md     | 256 +++++++
 .../d32406e872ba4eaa916cb75e0f7be239.stderr        |   8 +
 .../recovery-seatbelt-smoke-retry.jsonl            |   9 +
 .../recovery-seatbelt-smoke-retry.stderr           |   8 +
 .../recovery-seatbelt-smoke.jsonl                  |   6 +
 .../recovery-seatbelt-smoke.stderr                 |   8 +
 .../autopilot/dispatch-metrics.jsonl               |  62 ++
 .../autopilot/ledger/dispatch-metrics.jsonl        |  62 ++
 .../reports/00111-autocodex-seatbelt-repair.patch  | 197 ++++++
 ...bs-and-cancellation-v1-build-handoff-state.json | 353 ++++++++++
 ...ckup-parallel-jobs-and-cancellation-v1-build.md |  70 ++
 ...-and-cancellation-v1-implementation-models.json | 266 ++++++++
 ...bs-and-cancellation-v1-implementation-models.md |  55 ++
 ...llel-jobs-and-cancellation-v1-paused-state.json | 231 +++++++
 .../reports/00111-build-session-progress.md        |  28 +
 .../autopilot/reports/00111-design-review-1.json   |  22 +
 .../reports/00111-design-review-2-fallback.json    |  22 +
 .../autopilot/reports/00111-design-review-2.txt    |   1 +
 .../reports/00111-devon-1-failed-result.json       |  25 +
 .../autopilot/reports/00111-devon-1-result.json    |  62 ++
 .../autopilot/reports/00111-devon-infra.md         |  26 +
 .../reports/00111-host-execution-pause.md          |  88 +++
 .../00111-task-1-ivan-astra-model-metadata.jsonl   |   2 +
 .../00111-task-1-ivan-sol-model-metadata.jsonl     |   2 +
 .../reports/00111-task-1-pat-unavailable.md        |   1 +
 .../reports/00111-task-1-tess-model-metadata.jsonl |   2 +
 ...111-task-1-tess-strengthen-model-metadata.jsonl |   2 +
 .../autopilot/reports/00111-task-2-pat.md          |   1 +
 .../reports/00111-task-2-tess-model-metadata.jsonl |   2 +
 .../reports/00111-task-2-tess-result.json          |  40 ++
 .../reports/00111-task-3-pat-unavailable.md        |   1 +
 .../autopilot/reports/00111-verification-1.log     | 351 ++++++++++
 .../00111-verification-config/buvis-postup.yaml    |   1 +
 .../autopilot/reports/00111-verification-final.log | 137 ++++
 .../autopilot/reports/00111-verification-runner.py |  51 ++
 ...8efc-495c-7a12-ba9f-8a3f58558537-evidence.jsonl |   5 +
 ...8efc-495c-7a12-ba9f-8a3f58558537-metadata.jsonl |   4 +
 ...8efd-8e9c-7362-bcca-b0edc6dd19f5-evidence.jsonl |   6 +
 ...8efd-8e9c-7362-bcca-b0edc6dd19f5-metadata.jsonl |   4 +
 ...8eff-1159-7cc0-928a-9b5eb6492209-evidence.jsonl |   7 +
 ...8eff-1159-7cc0-928a-9b5eb6492209-metadata.jsonl |   4 +
 ...8f01-dfbd-7ed2-b852-7df2cc134eea-evidence.jsonl |   6 +
 ...8f01-dfbd-7ed2-b852-7df2cc134eea-metadata.jsonl |   4 +
 ...8f02-f071-7d32-9e68-1eba07667d8e-evidence.jsonl |   7 +
 ...8f02-f071-7d32-9e68-1eba07667d8e-metadata.jsonl |   4 +
 ...8f06-87f0-7852-b6d9-1e329ac76366-evidence.jsonl |   6 +
 ...8f06-87f0-7852-b6d9-1e329ac76366-metadata.jsonl |   4 +
 ...8f08-3dc4-7a23-a34b-e2de768e4119-evidence.jsonl |   5 +
 ...8f08-3dc4-7a23-a34b-e2de768e4119-metadata.jsonl |   4 +
 ...8f09-c6c1-7312-a3d8-72e383d58128-metadata.jsonl |   4 +
 ...8f0e-6eb5-7463-a886-de08e23467a3-metadata.jsonl |   4 +
 ...8f11-bf65-7610-8850-3ddaddf172db-metadata.jsonl |   4 +
 ...8f14-dd62-7b22-a484-d2af75f2fff6-metadata.jsonl |   4 +
 ...8f17-6cd6-7091-8236-39aef9e5d843-metadata.jsonl |   4 +
 ...8f19-340e-7e70-8fb6-3619d14f51c0-metadata.jsonl |   4 +
 ...8f1a-d487-71e2-85f0-defa6a880626-metadata.jsonl |   4 +
 ...8f1b-e4a1-7d93-9b7f-9256b97f5fe4-metadata.jsonl |   6 +
 ...8f22-0de4-71c0-981f-c6a7c67ea04c-metadata.jsonl |   4 +
 ...8f23-ef76-7d30-8ba3-267820ccc5fe-metadata.jsonl |   4 +
 ...kup-parallel-jobs-and-cancellation-v1-design.md | 212 ++++++
 docs/dev/project-management/meta/assumptions.md    |  31 +-
 ...111-backup-parallel-jobs-and-cancellation-v1.md |   0
 docs/source/tools/backup.rst                       |  21 +-
 src/tools/backup/capabilities/tar_archive.py       | 145 ++--
 src/tools/backup/cli.py                            | 102 +--
 src/tools/backup/runner.py                         | 130 +++-
 .../bim/commands/serve/frontend/package-lock.json  | 364 +++++-----
 src/tools/bim/commands/serve/frontend/package.json |   2 +-
 .../postup/adapters/web/frontend/package-lock.json |   8 +-
 .../postup/adapters/web/frontend/package.json      |   2 +-
 tests/tools/backup/parallel_runner_helpers.py      | 108 +++
 tests/tools/backup/test_backup_cli.py              |  32 +-
 tests/tools/backup/test_backup_phase2.py           |  17 +-
 tests/tools/backup/test_instance_excludes.py       |   2 +-
 tests/tools/backup/test_parallel_cli.py            | 305 +++++++++
 tests/tools/backup/test_parallel_runner.py         | 748 +++++++++++++++++++++
 .../tools/backup/test_parallel_runner_lifecycle.py | 191 ++++++
 tests/tools/backup/test_plan_errors.py             |  14 +-
 tests/tools/backup/test_plan_runner.py             |  37 +-
 tests/tools/backup/test_plan_validation.py         |  23 +-
 87 files changed, 6058 insertions(+), 349 deletions(-)
```

### Diff Content
Full diff available at: /Users/bob/git/src/github.com/buvis/gems/docs/dev/tmp/review-diff-00111-c1-20261031.diff

(7574 lines)

## PRD Requirements

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

## Mechanical facts (computed, do not re-count)

Function line counts from `ast`. Cite these for countable claims; a
finding that contradicts this block is discarded at the review gate.

- `CHANGELOG.md` — skipped (non-python)
- `README.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/a3e2a400dac044409603bd60651ac053.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/a3e2a400dac044409603bd60651ac053.prompt.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/a3e2a400dac044409603bd60651ac053.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/d32406e872ba4eaa916cb75e0f7be239.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/d32406e872ba4eaa916cb75e0f7be239.prompt.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/d32406e872ba4eaa916cb75e0f7be239.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/recovery-seatbelt-smoke-retry.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/recovery-seatbelt-smoke-retry.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/recovery-seatbelt-smoke.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/recovery-seatbelt-smoke.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/dispatch-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/ledger/dispatch-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-autocodex-seatbelt-repair.patch` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-backup-parallel-jobs-and-cancellation-v1-build-handoff-state.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-backup-parallel-jobs-and-cancellation-v1-build.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-backup-parallel-jobs-and-cancellation-v1-implementation-models.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-backup-parallel-jobs-and-cancellation-v1-implementation-models.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-backup-parallel-jobs-and-cancellation-v1-paused-state.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-build-session-progress.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-design-review-1.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-design-review-2-fallback.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-design-review-2.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-devon-1-failed-result.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-devon-1-result.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-devon-infra.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-host-execution-pause.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-1-ivan-astra-model-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-1-ivan-sol-model-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-1-pat-unavailable.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-1-tess-model-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-1-tess-strengthen-model-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-2-pat.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-2-tess-model-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-2-tess-result.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-task-3-pat-unavailable.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-verification-1.log` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-verification-config/buvis-postup.yaml` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-verification-final.log` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-verification-runner.py`
  - `main` — line 12, 36 lines
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18efc-495c-7a12-ba9f-8a3f58558537-evidence.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18efc-495c-7a12-ba9f-8a3f58558537-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18efd-8e9c-7362-bcca-b0edc6dd19f5-evidence.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18efd-8e9c-7362-bcca-b0edc6dd19f5-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18eff-1159-7cc0-928a-9b5eb6492209-evidence.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18eff-1159-7cc0-928a-9b5eb6492209-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f01-dfbd-7ed2-b852-7df2cc134eea-evidence.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f01-dfbd-7ed2-b852-7df2cc134eea-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f02-f071-7d32-9e68-1eba07667d8e-evidence.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f02-f071-7d32-9e68-1eba07667d8e-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f06-87f0-7852-b6d9-1e329ac76366-evidence.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f06-87f0-7852-b6d9-1e329ac76366-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f08-3dc4-7a23-a34b-e2de768e4119-evidence.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f08-3dc4-7a23-a34b-e2de768e4119-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f09-c6c1-7312-a3d8-72e383d58128-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f0e-6eb5-7463-a886-de08e23467a3-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f11-bf65-7610-8850-3ddaddf172db-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f14-dd62-7b22-a484-d2af75f2fff6-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f17-6cd6-7091-8236-39aef9e5d843-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f19-340e-7e70-8fb6-3619d14f51c0-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f1a-d487-71e2-85f0-defa6a880626-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f1b-e4a1-7d93-9b7f-9256b97f5fe4-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f22-0de4-71c0-981f-c6a7c67ea04c-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00111-worker-01a18f23-ef76-7d30-8ba3-267820ccc5fe-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/designs/00111-backup-parallel-jobs-and-cancellation-v1-design.md` — skipped (non-python)
- `docs/dev/project-management/meta/assumptions.md` — skipped (non-python)
- `docs/dev/project-management/prds/wip/00111-backup-parallel-jobs-and-cancellation-v1.md` — skipped (non-python)
- `docs/source/tools/backup.rst` — skipped (non-python)
- `src/tools/backup/capabilities/tar_archive.py`
  - `_check_cancel` — line 36, 3 lines
  - `WalkResult.__init__` — line 53, 11 lines
  - `WalkResult.file_count` — line 66, 2 lines
  - `TarArchive.inputs` — line 83, 2 lines
  - `TarArchive.plan` — line 86, 36 lines
  - `TarArchive.run` — line 123, 30 lines
  - `TarArchive._run_validated` — line 154, 39 lines
  - `TarArchive._dry_run_result` — line 195, 12 lines
  - `TarArchive._archive_result` — line 209, 22 lines
  - `_reject_out_inside_source` — line 233, 20 lines
  - `_normalize_items` — line 255, 16 lines
  - `_select_items` — line 273, 38 lines
  - `_walk_tree` — line 313, 70 lines
  - `_raise_walk_error` — line 385, 8 lines
  - `_collect_applied` — line 395, 8 lines
  - `_write_archive` — line 405, 30 lines
  - `_write_archive_system_tar` — line 437, 49 lines
  - `_run_system_tar` — line 488, 32 lines
  - `_cleanup_tar_process` — line 522, 17 lines
  - `_parse_inputs` — line 541, 9 lines
  - `_missing_input` — line 552, 5 lines
  - `_resolve_paths` — line 559, 9 lines
  - `_require_str` — line 570, 3 lines
  - `_expand_stamp` — line 575, 10 lines
  - `_as_str_tuple` — line 587, 4 lines
- `src/tools/backup/cli.py`
  - `_report_step` — line 19, 8 lines
  - `_report_steps` — line 29, 35 lines
  - `_parse_only` — line 66, 5 lines
  - `_describe` — line 73, 3 lines
  - `_apply_overrides` — line 78, 13 lines
  - `_override_selected` — line 93, 12 lines
  - `_list_instances` — line 107, 6 lines
  - `_load_config` — line 115, 17 lines
  - `_show_excludes` — line 134, 50 lines
  - `_select_plan` — line 186, 31 lines
  - `_run_plan` — line 219, 36 lines
  - `cli` — line 275, 49 lines
- `src/tools/backup/runner.py`
  - `Runner.__init__` — line 35, 11 lines
  - `Runner.request_cancel` — line 47, 5 lines
  - `Runner.run` — line 53, 31 lines
  - `Runner._execute` — line 85, 45 lines
  - `Runner._shutdown` — line 131, 7 lines
  - `Runner._cancelled_result` — line 139, 4 lines
  - `Runner.plan` — line 144, 2 lines
  - `Runner._plan` — line 147, 41 lines
  - `Runner._run_instance` — line 189, 21 lines
- `src/tools/bim/commands/serve/frontend/package-lock.json` — skipped (non-python)
- `src/tools/bim/commands/serve/frontend/package.json` — skipped (non-python)
- `src/tools/postup/adapters/web/frontend/package-lock.json` — skipped (non-python)
- `src/tools/postup/adapters/web/frontend/package.json` — skipped (non-python)
- `tests/tools/backup/parallel_runner_helpers.py`
  - `CapabilityProbe.__init__` — line 23, 11 lines
  - `CapabilityProbe.plan` — line 35, 4 lines
  - `CapabilityProbe.run` — line 40, 13 lines
  - `CapabilityProbe.blocked` — line 54, 4 lines
  - `CapabilityProbe.release_all` — line 59, 3 lines
  - `configure` — line 64, 12 lines
  - `Consumption.__init__` — line 79, 7 lines
  - `Consumption.collect` — line 87, 8 lines
  - `Consumption.__enter__` — line 96, 3 lines
  - `Consumption.finish` — line 100, 4 lines
  - `Consumption.__exit__` — line 105, 4 lines
- `tests/tools/backup/test_backup_cli.py`
  - `_cfg` — line 18, 2 lines
  - `_steps` — line 22, 2 lines
  - `TestBackupCliShape.test_cli_is_a_single_command_not_a_group` — line 27, 3 lines
  - `TestBackupCliShape.test_help_lists_filters` — line 31, 7 lines
  - `TestBackupCliRun.test_runs_all_applicable_and_renders_via_console` — line 41, 13 lines
  - `TestBackupCliRun.test_only_narrows_selection` — line 55, 17 lines
  - `TestBackupCliRun.test_only_narrows_selection._fake_run` — line 60, 3 lines
  - `TestBackupCliRun.test_tag_narrows_selection` — line 73, 22 lines
  - `TestBackupCliRun.test_tag_narrows_selection._fake_run` — line 83, 3 lines
  - `TestBackupCliRun.test_only_unknown_reports` — line 96, 12 lines
  - `TestBackupCliList.test_list_prints_plan_and_runs_nothing` — line 111, 12 lines
  - `TestBackupCliList.test_list_empty_plan` — line 124, 9 lines
  - `TestBackupCliDryRun.test_dry_run_passes_flag_to_runner` — line 136, 12 lines
  - `TestBackupCliErrors.test_config_fatal_error_panics_not_traceback` — line 151, 7 lines
  - `TestBackupCliExitCode.test_failing_step_exits_nonzero_but_renders_all` — line 164, 19 lines
  - `TestBackupCliExitCode.test_all_success_exits_zero` — line 184, 12 lines
  - `TestBackupCliForGuard.test_for_without_show_excludes_does_not_run_and_reports` — line 202, 11 lines
  - `TestBackupCliForGuard.test_show_excludes_with_for_still_works` — line 214, 10 lines
  - `TestShowExcludesExitCode.test_unknown_instance_exits_nonzero` — line 230, 6 lines
  - `TestShowExcludesExitCode.test_instance_without_source_exits_nonzero` — line 237, 6 lines
  - `TestShowExcludesExitCode.test_known_instance_exits_zero` — line 244, 5 lines
  - `TestOnlyUnknownExitCode.test_all_unknown_only_exits_nonzero_and_runs_nothing` — line 255, 12 lines
  - `TestOnlyUnknownExitCode.test_partial_unknown_only_still_runs_valid_but_exits_nonzero` — line 268, 12 lines
  - `TestOnlyUnknownExitCode.test_list_with_unknown_only_exits_nonzero` — line 281, 9 lines
  - `TestBackupConfigSelectionThreaded._isolate` — line 301, 8 lines
  - `TestBackupConfigSelectionThreaded.test_config_file_supplies_the_plan` — line 310, 19 lines
  - `TestBackupConfigSelectionThreaded.test_config_file_hides_discovered_user_config` — line 330, 39 lines
  - `TestBackupConfigSelectionThreaded.test_config_dir_supplies_the_plan` — line 370, 20 lines
  - `TestBackupConfigSelectionThreaded.test_no_selection_uses_default_plan` — line 391, 9 lines
  - `TestBackupCliSkipSummary.test_skip_summary_counts_every_step_and_only_failures_change_exit_status` — line 415, 47 lines
  - `TestBackupCliSkipSummary.test_empty_run_summary_has_zero_counts` — line 464, 10 lines
- `tests/tools/backup/test_backup_phase2.py`
  - `_tree` — line 12, 6 lines
  - `_archive_members` — line 20, 3 lines
  - `_run_engine` — line 25, 13 lines
  - `_cfg` — line 40, 2 lines
  - `TestSourceOutOverride.test_source_and_out_override_selected_instance` — line 45, 20 lines
  - `TestSourceOutOverride.test_source_and_out_override_selected_instance._fake_run` — line 52, 4 lines
  - `TestSourceOutOverride.test_flag_wins_over_config_value` — line 66, 18 lines
  - `TestSourceOutOverride.test_flag_wins_over_config_value._fake_run` — line 70, 3 lines
  - `TestSourceOutOverride.test_multiple_instances_with_override_is_usage_error` — line 85, 14 lines
  - `TestShowExcludes.test_show_excludes_for_reflects_unignore` — line 102, 16 lines
  - `TestShowExcludes.test_show_excludes_writes_no_archive` — line 119, 12 lines
  - `TestShowExcludes.test_show_excludes_without_for_prints_global_and_note` — line 132, 13 lines
  - `TestSystemTarEngine.test_system_tar_member_names_match_python_engine` — line 148, 19 lines
  - `TestSystemTarEngine.test_missing_tar_falls_back_to_python_with_note` — line 168, 10 lines
  - `TestSystemTarEngine.test_failing_tar_falls_back_to_python_with_note` — line 179, 18 lines
  - `TestSystemTarEngine.test_newline_in_filename_does_not_inject_and_engines_agree` — line 198, 26 lines
  - `TestEngineValidation.test_unknown_engine_rejected_without_archiving` — line 227, 18 lines
  - `TestEngineValidation.test_unknown_engine_rejected_in_dry_run` — line 246, 16 lines
  - `TestTotalBytesMeaning.test_real_run_total_bytes_is_input_bytes` — line 265, 12 lines
  - `TestV1Regression.test_no_flags_behaves_as_v1` — line 280, 18 lines
  - `TestV1Regression.test_default_engine_unset_matches_v1_output` — line 299, 13 lines
- `tests/tools/backup/test_instance_excludes.py`
  - `_tree` — line 15, 5 lines
  - `_config_file` — line 22, 5 lines
  - `_archive_members` — line 29, 3 lines
  - `TestInstanceExcludeFields.test_defaults_inherit_without_additions_or_removals` — line 35, 5 lines
  - `TestInstanceExcludeFields.test_loads_instance_fields_beside_with` — line 42, 19 lines
  - `TestInstanceExcludeFields.test_unknown_instance_key_raises_fatal` — line 63, 4 lines
  - `TestInstanceExcludeFields.test_exclude_fields_inside_with_are_rejected` — line 69, 4 lines
  - `TestEffectiveExcludes.test_effective_excludes_keep_first_occurrence_in_order` — line 101, 9 lines
  - `TestRunnerInstanceExcludes.test_runner_add_and_remove_affect_only_selected_instance` — line 124, 39 lines
  - `TestRunnerInstanceExcludes.test_inherit_false_keeps_build_dirs` — line 172, 42 lines
  - `TestShowInstanceExcludes.test_show_excludes_prints_effective_list_and_resolves_bkpignore` — line 237, 41 lines
  - `TestShowInstanceExcludes.test_show_excludes_accepts_empty_effective_list` — line 279, 14 lines
- `tests/tools/backup/test_parallel_cli.py`
  - `_capture_console` — line 21, 16 lines
  - `_capture_console.sink` — line 26, 8 lines
  - `_capture_console.sink.render` — line 27, 5 lines
  - `_rows` — line 39, 2 lines
  - `test_cli_report_retries_interrupted_render_without_losing_steps_or_double_counting` — line 46, 25 lines
  - `test_cli_report_retries_interrupted_render_without_losing_steps_or_double_counting.interrupt` — line 60, 5 lines
  - `test_cli_report_empty_or_successful_run_returns_false_and_propagates_interrupt_without_callback` — line 74, 11 lines
  - `_InterruptedInput.__init__` — line 88, 3 lines
  - `_InterruptedInput.__iter__` — line 92, 2 lines
  - `_InterruptedInput.__next__` — line 95, 5 lines
  - `test_cli_report_drains_same_iterator_after_repeated_interrupts_while_fetching` — line 103, 15 lines
  - `_interruptible_probe` — line 120, 18 lines
  - `_interruptible_probe.behavior` — line 124, 11 lines
  - `test_cli_interrupt_retries_published_step_drains_workers_and_retries_exit_130_message` — line 141, 26 lines
  - `test_cli_interrupt_retries_published_step_drains_workers_and_retries_exit_130_message.interrupt` — line 149, 5 lines
  - `test_cli_interrupt_after_completed_work_reports_no_unfinished_instances` — line 170, 28 lines
  - `test_cli_interrupt_after_completed_work_reports_no_unfinished_instances.interrupt` — line 183, 5 lines
  - `test_cli_unrelated_render_exception_closes_generator_and_joins_active_workers` — line 200, 16 lines
  - `test_cli_unrelated_render_exception_closes_generator_and_joins_active_workers.fail_render` — line 206, 3 lines
  - `test_cli_preserves_success_failure_and_unknown_selector_exit_codes` — line 229, 34 lines
  - `test_cli_preserves_success_failure_and_unknown_selector_exit_codes.behavior` — line 244, 3 lines
  - `test_cli_loads_ordinary_yaml_and_keeps_standard_options_available` — line 265, 24 lines
  - `test_cli_rejects_unknown_capability_inputs_before_running_writers` — line 291, 15 lines
- `tests/tools/backup/test_parallel_runner.py`
  - `_members` — line 33, 11 lines
  - `_assert_output` — line 46, 5 lines
  - `_require_archive_fsync_before_publication` — line 53, 16 lines
  - `_require_archive_fsync_before_publication.sync` — line 57, 4 lines
  - `_require_archive_fsync_before_publication.replace` — line 62, 4 lines
  - `_stub_tar` — line 71, 23 lines
  - `_cancel_after_start` — line 96, 10 lines
  - `_cancel_after_start.watch` — line 97, 5 lines
  - `tar_children` — line 109, 15 lines
  - `tar_children.spawn` — line 113, 4 lines
  - `TestPythonArchiveCancellation.test_cancel_cleans_after_current_member_without_adding_the_next` — line 128, 26 lines
  - `TestPythonArchiveCancellation.test_cancel_cleans_after_current_member_without_adding_the_next.add` — line 143, 4 lines
  - `TestPythonArchiveCancellation.test_cancel_cleans_when_iterable_finishes_even_without_members` — line 156, 15 lines
  - `TestPythonArchiveCancellation.test_cancel_cleans_when_iterable_finishes_even_without_members.selected` — line 163, 3 lines
  - `TestPythonArchiveCancellation.test_cancel_cleans_when_requested_during_fsync` — line 173, 22 lines
  - `TestPythonArchiveCancellation.test_cancel_cleans_when_requested_during_fsync.sync` — line 186, 3 lines
  - `TestPythonArchiveCancellation.test_uncancelled_writer_publishes_exact_members_with_private_permissions` — line 198, 20 lines
  - `TestSystemArchiveCancellation.test_terminates_tar_and_cancel_cleans_without_fallback` — line 223, 35 lines
  - `TestSystemArchiveCancellation.test_polling_timeouts_retry_without_input_and_do_not_trigger_python_fallback` — line 259, 40 lines
  - `TestSystemArchiveCancellation.test_polling_timeouts_retry_without_input_and_do_not_trigger_python_fallback.communicate` — line 274, 3 lines
  - `TestSystemArchiveCancellation.test_cancel_cleans_before_spawn_when_member_iteration_sets_event` — line 301, 24 lines
  - `TestSystemArchiveCancellation.test_cancel_cleans_before_spawn_when_member_iteration_sets_event.selected` — line 313, 3 lines
  - `TestSystemArchiveCancellation.test_cancel_cleans_before_spawn_when_member_iteration_sets_event.unexpected_spawn` — line 317, 2 lines
  - `TestSystemArchiveCancellation.test_cancel_cleans_after_child_exits_without_publishing` — line 327, 30 lines
  - `TestSystemArchiveCancellation.test_cancel_cleans_after_child_exits_without_publishing.communicate` — line 345, 3 lines
  - `TestCapabilityArchiveCancellation.test_already_cancelled_capability_does_not_select_members_or_create_output` — line 361, 22 lines
  - `TestCapabilityArchiveCancellation.test_already_cancelled_capability_does_not_select_members_or_create_output.unexpected_walk` — line 372, 2 lines
  - `TestCapabilityArchiveCancellation.test_capability_forwards_cancellation_to_selected_engine_or_legitimate_fallback` — line 385, 31 lines
  - `TestCapabilityArchiveCancellation.test_capability_forwards_cancellation_to_selected_engine_or_legitimate_fallback.add` — line 397, 3 lines
  - `TestCapabilityArchiveCancellation.test_capability_forwards_cancellation_to_selected_engine_or_legitimate_fallback.unavailable` — line 401, 2 lines
  - `TestCapabilityArchiveCancellation.test_cancel_cleans_temp_files_both_engines` — line 418, 44 lines
  - `TestCapabilityArchiveCancellation.test_cancel_cleans_temp_files_both_engines.add` — line 433, 5 lines
  - `TestParallelRunner.test_jobs_rejects_nonpositive_limits` — line 466, 4 lines
  - `TestParallelRunner.test_never_exceeds_jobs` — line 472, 18 lines
  - `TestParallelRunner.test_jobs_one_runs_strictly_in_order` — line 491, 13 lines
  - `TestParallelRunner.test_order_follows_completion_while_preserving_each_instances_steps` — line 505, 28 lines
  - `TestParallelRunner.test_order_follows_completion_while_preserving_each_instances_steps.steps` — line 511, 5 lines
  - `TestParallelRunner.test_failure_isolated_from_other_workers` — line 535, 18 lines
  - `TestParallelRunner.test_failure_isolated_from_other_workers.fail_one` — line 539, 5 lines
  - `TestParallelRunner.test_interrupt_cancels_active_and_unsubmitted_but_preserves_committed_success` — line 554, 38 lines
  - `TestParallelRunner.test_interrupt_cancels_active_and_unsubmitted_but_preserves_committed_success.interruptible` — line 560, 10 lines
  - `TestParallelRunner.test_interrupt_keyboard_at_yield_drains_workers_without_reraising` — line 593, 34 lines
  - `TestParallelRunner.test_interrupt_keyboard_at_yield_drains_workers_without_reraising.interruptible` — line 599, 10 lines
  - `TestParallelRunner.test_interrupt_generator_close_joins_active_workers_and_prevents_refill` — line 628, 29 lines
  - `TestParallelRunner.test_interrupt_generator_close_joins_active_workers_and_prevents_refill.interruptible` — line 635, 11 lines
  - `TestCliParallelJobs.test_cli_rejects_invalid_jobs_before_loading_config_or_early_modes` — line 662, 12 lines
  - `TestCliParallelJobs.test_cli_forwards_default_and_explicit_jobs_to_real_scheduling` — line 677, 47 lines
  - `TestCliParallelJobs.test_cli_forwards_default_and_explicit_jobs_to_real_scheduling.release_batch` — line 695, 9 lines
  - `TestCliParallelJobs.test_cli_plan_keeps_writers_and_executor_unused_with_jobs` — line 726, 23 lines
  - `TestCliParallelJobs.test_cli_plan_keeps_writers_and_executor_unused_with_jobs.reject_executor` — line 738, 2 lines
- `tests/tools/backup/test_parallel_runner_lifecycle.py`
  - `TestParallelRunnerLifecycle.test_workers_share_run_event_and_clock_without_mutating_instance_kwargs` — line 17, 36 lines
  - `TestParallelRunnerLifecycle.test_workers_share_run_event_and_clock_without_mutating_instance_kwargs.mutate_local` — line 26, 5 lines
  - `TestParallelRunnerLifecycle.test_instance_runtime_values_override_with_options_and_pre_cancel_prevents_invocation` — line 55, 29 lines
  - `TestParallelRunnerLifecycle.test_preflight_failures_precede_worker_results_and_skips_remain_skips` — line 85, 21 lines
  - `TestParallelRunnerLifecycle.test_preflight_failures_precede_worker_results_and_skips_remain_skips.outcomes` — line 92, 3 lines
  - `TestParallelRunnerLifecycle.test_preflight_fatal_error_propagates_before_any_worker_starts` — line 108, 12 lines
  - `TestParallelRunnerLifecycle.test_preflight_fatal_error_propagates_before_any_worker_starts.FatalProbe.plan` — line 112, 2 lines
  - `TestParallelRunnerLifecycle.test_request_cancel_after_completion_and_successive_empty_run_reset_state` — line 121, 23 lines
  - `TestParallelRunnerLifecycle.test_interrupt_preserves_completed_results_not_yet_collected` — line 145, 30 lines
  - `TestParallelRunnerLifecycle.test_interrupt_preserves_completed_results_not_yet_collected.finish` — line 150, 7 lines
  - `TestParallelRunnerLifecycle.test_interrupt_during_preflight_marks_every_unsubmitted_instance_cancelled` — line 176, 16 lines
  - `TestParallelRunnerLifecycle.test_interrupt_during_preflight_marks_every_unsubmitted_instance_cancelled.InterruptedProbe.plan` — line 180, 2 lines
- `tests/tools/backup/test_plan_errors.py`
  - `_config` — line 20, 8 lines
  - `_fail_metadata` — line 30, 9 lines
  - `_fail_metadata.stat` — line 33, 4 lines
  - `_assert_archive` — line 41, 6 lines
  - `test_runner_isolates_metadata_failures_and_preserves_independent_instances` — line 52, 45 lines
  - `test_runner_rejects_every_duplicate_output_even_when_member_metadata_fails` — line 102, 45 lines
  - `test_runner_propagates_the_original_fatal_metadata_error` — line 152, 19 lines
  - `test_runner_keeps_empty_selection_empty_without_planning_unselected_instances` — line 174, 16 lines
  - `test_runner_rejects_timestamp_output_collisions_when_source_metadata_fails` — line 195, 52 lines
- `tests/tools/backup/test_plan_runner.py`
  - `_config` — line 21, 8 lines
  - `_assert_archive` — line 31, 6 lines
  - `_record_archive_creation` — line 39, 11 lines
  - `_record_archive_creation.record_open` — line 43, 4 lines
  - `test_runner_duplicate_groups_reject_all_members_and_keep_independent_outputs` — line 53, 49 lines
  - `test_runner_duplicate_comparison_expands_home_and_normalizes_components` — line 106, 36 lines
  - `test_runner_duplicate_guard_compares_timestamp_expanded_outputs` — line 146, 29 lines
  - `test_runner_duplicate_guard_considers_only_selected_instances` — line 178, 17 lines
  - `test_runner_empty_selection_returns_no_steps_and_creates_no_output` — line 198, 10 lines
  - `test_runner_shares_one_clock_per_call_and_refreshes_between_run_and_plan` — line 212, 38 lines
  - `test_runner_preserves_capability_inputs_and_surfaces_validation_failures` — line 260, 30 lines
  - `test_runner_preserves_global_and_instance_exclusion_rules` — line 293, 37 lines
  - `test_runner_preserves_multiple_literal_items_without_archiving_lookalikes` — line 332, 23 lines
  - `test_runner_returns_failed_result_for_execution_fatal_archive_filesystem_errors` — line 358, 12 lines
  - `test_runner_preserves_missing_source_skips_and_existing_outputs` — line 373, 24 lines
  - `test_runner_preserves_supported_engine_choices_and_fallback_messages` — line 400, 17 lines
- `tests/tools/backup/test_plan_validation.py`
  - `_source` — line 21, 6 lines
  - `_invoke` — line 29, 10 lines
  - `_assert_archive` — line 41, 8 lines
  - `_snapshot` — line 51, 2 lines
  - `test_empty_engine_matches_omitted_python_engine` — line 58, 26 lines
  - `test_empty_paths_fail_without_using_cwd_or_changing_artifacts` — line 90, 29 lines
  - `_mixed_config` — line 121, 16 lines
  - `test_runner_keeps_missing_inputs_distinct_from_collisions_and_executes_independent_instances` — line 140, 40 lines
  - `test_engine_lookalikes_remain_rejected_without_archive_effects` — line 185, 17 lines
  - `test_fatal_archive_errors_follow_interface_contract_with_empty_default_engine` — line 206, 23 lines
  - `test_runner_empty_selection_has_no_archive_effects` — line 232, 12 lines

## Tautological test shapes (computed, do not re-judge)

Each `[MECH]` line is a test whose shape cannot fail as written. Raise
it; step 6 adds any line the table lacks. `mech-check` is the finder.


Checked 111 test function(s) in 9 test file(s).

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `9a7f78c8eb0e`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.

[MECH] 🟡 18 touched test(s) pass against the pre-change code: test_runner_rejects_every_duplicate_output_even_when_member_metadata_fails +12 more | File: tests/tools/backup/test_plan_errors.py | Task: general
[MECH] 🟡 9 touched test(s) pass against the pre-change code: test_runner_duplicate_groups_reject_all_members_and_keep_independent_outputs, test_runner_preserves_global_and_instance_exclusion_rules, test_runner_preserves_multiple_literal_items_without_archiving_lookalikes +3 more | File: tests/tools/backup/test_plan_runner.py | Task: general
[MECH] 🟡 3 touched test(s) pass against the pre-change code: test_runner_keeps_missing_inputs_distinct_from_collisions_and_executes_independent_instances | File: tests/tools/backup/test_plan_validation.py | Task: general

Replay: 56 touched test(s) ran, 26 failed against base, 30 passed; 6 test file(s) could not be collected at base (their tests fail there). Command: uv run pytest

## Context Pack

Pack file: /Users/bob/git/src/github.com/buvis/gems/docs/dev/tmp/engram-pack-00111-c1-20261031.md

### Findings precedent

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  Pat (`agents/pat.md` rendered by `render_prompt.py`, Sonnet lane, `sonnet-run.sh -t ""`, no tools) reviewed `11f54ac..ba8e7b8` against the quoted findings and the recorded verification. Output: `docs/dev/tmp/review-task-00005c1rw.md`.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  # Review: 00012-autopilot-package-contract-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/tmp/blake-output-ap00012-c1.txt.receipt.json

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  | R17 | [1/3] | ⚪ | The draft 2020-12 `"type":"integer"` accepts `1.0`, so `attempt: 1.0` passes the schema. The oracle's `range(1, highest + 1)` would then likely raise TypeError instead of returning a defect. The wire test covers 1.5 but not 1.0. | tests/autopilot/test_contract_semantics.py:160 | 3 | BOB |

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  The high resource-edge gap blocks convergence at cycle1/cap3. Existing schema suffices; additive source-anchored dependency rows and tests need no new dependency, external interface or foundational data-model decision. Original completed tasks stay completed. Queue fresh D1 follow-ups through review-close, preserving every prior implementation attempt and the model audit snapshot.

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00020-changelog-skill-presence-check-v1-review-2.md
  `01a077ec-1aa8-7ef1-96ba-8ed4aab0f82a`)

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00058-page-links-accept-javascript-urls-v1-review-1.md
  Fact-Forcing Gate (`gateguard`) — `error=Command blocked by PreToolUse hook:

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00111-braid-state-misses-link-removals-v1-review-2.md
  1, "You have exceeded your monthly quota". Retried once per retry policy, same

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00093-cut-build-phase-clerical-overhead-v1-review-1.md
  [BOB] 🟡 Completed tasks are counted as transition calls rather than distinct task IDs, so duplicate completion updates deflate the ratio | File: .claude/skills/work/scripts/check_build_overhead.py:88 | Task: 7

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00171-route-sonnet-prompt-through-stdin-v1-review-1.md
  `CODEX_SESSION_ID` is what the build phase worked around when it ran

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-02.md
  ## Follow-up work

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-03.md
  ```

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00183-make-batch-report-decisions-and-implementor-mix-render-v1-review-2.md
  # Review: 00183-make-batch-report-decisions-and-implementor-mix-render-v1

## Test gate

Tests: counts unavailable (suite run this cycle, exit 1, no PASS/FAIL/SKIP/EXIT summary line)
