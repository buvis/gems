---
catchup: skip
design: skip
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
- **Inputs**: `--jobs N` (`click.IntRange(min=1)`, default 3); `Runner(cfg, dry_run=..., jobs=N)`.
- **Outputs**: instances run on a `concurrent.futures.ThreadPoolExecutor(max_workers=jobs)` in `(order, name)` submit order; `--jobs 1` is sequential.
- **Behavior**: order is launch priority only, not a completion barrier. Results are yielded to the caller in completion order, from the calling thread only; workers never write to the console. A worker exception becomes a failed `StepResult` for that instance and does not stop the others. Instances rejected by PRD 00110's duplicate check are never submitted.

### Capability: Cancellation
Stop everything cleanly on interrupt.

#### Feature: Cooperative cancel signal
- **Description**: A `threading.Event` named `cancel` is passed to every capability call as the kwarg `cancel`.
- **Inputs**: `cancel: threading.Event`.
- **Outputs**: raising `ArchiveCancelled` (new exception in `src/tools/backup/capabilities/tar_archive.py`) from the Python writer, checked before each member is added, after which the existing `except BaseException` cleanup removes the temp file.
- **Behavior**: the system-tar writer starts tar with `subprocess.Popen` and waits with a loop of `process.communicate(input=..., timeout=0.2)` retries, checking `cancel` between retries; on cancel it calls `process.terminate()`, then `process.kill()` if it has not exited after 5 seconds, waits, removes the temp file, and raises `ArchiveCancelled`. `ArchiveCancelled` is not turned into a fallback to the Python engine.

#### Feature: Interrupt handling
- **Description**: Ctrl-C in the CLI stops the run.
- **Inputs**: `KeyboardInterrupt` in the calling thread while waiting for results.
- **Outputs**: `cancel` set; no new instance starts (`executor.shutdown(wait=True, cancel_futures=True)`); every still-active writer cleans up; completed archives and prior outputs are untouched; the CLI prints `console.failure("interrupted: ...")` naming the instances that did not finish, and exits 130.
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
- [ ] Add `--jobs` and the exit-130 path to `src/tools/backup/cli.py` (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/backup/test_parallel_runner.py -k cli -q` passes, including `--jobs 0` exiting 2 (click usage error).
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
