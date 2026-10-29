---
catchup: skip
design: skip
default_model: opus
model_tier_rationale: progress events cross worker threads into the calling thread; ordering and honest percentages decide correctness
---

# backup: live progress and --quiet

Source: `docs/dev/project-management/intake/processed/00107-backup-multi-source-parallel/discovery.md` (Q8). Depends on PRD 00111 (worker pool, `Runner(jobs=...)`) and PRD 00110.

## Overview

### Problem Statement
A long archive shows nothing until it ends: the CLI prints one result line per instance after the fact (`_report_step` in `src/tools/backup/cli.py`). With parallel jobs the operator cannot tell which archives are running, stuck or nearly done. A percentage derived from the compressed output size would be wrong, since compressed bytes are not input bytes.

### Target Users
The solo operator who watches a long interactive run and the cron job that must stay quiet.

### Success Metrics
- `uv run pytest tests/tools/backup/test_progress.py -q` passes.
- `test_percent_uses_input_bytes_not_output_size` passes: with an incompressible and a highly compressible fixture, the reported done bytes equal the summed sizes of the files added.
- `test_no_live_output_when_not_a_tty_or_quiet` passes: final result lines and the summary are still printed.

## Functional Decomposition

### Capability: Progress events
Capabilities report phase and measurable progress; the runner delivers them on the calling thread.

#### Feature: ProgressEvent
- **Description**: A small record emitted by a capability.
- **Inputs**: `label`, `phase` in `{scanning, archiving, finalizing}`, `done_bytes: int | None`, `total_bytes: int | None`.
- **Outputs**: `ProgressEvent` NamedTuple in `src/tools/backup/step_result.py`.
- **Behavior**: `done_bytes` and `total_bytes` are input bytes (sum of regular-file sizes), `None` when not measurable.

#### Feature: Engine reporting
- **Description**: `TarArchive.run` accepts a `progress` callable kwarg and calls it.
- **Inputs**: `progress: Callable[[ProgressEvent], None] | None`.
- **Outputs**: `scanning` before the walk; `archiving` after the walk with `total_bytes = walk.total_bytes`; for the Python engine, further `archiving` events carrying cumulative `done_bytes` (sum of `st_size` of regular files added so far), at most one per 0.2 seconds; `finalizing` after the archive stream closes. The system-tar engine emits `archiving` with `done_bytes=None` (activity only, no percentage) and the same `scanning` and `finalizing` events.
- **Behavior**: `progress` is never called for `dry_run`; a callback exception is swallowed so progress can never fail an archive.

#### Feature: Delivery to the calling thread
- **Description**: `Runner(cfg, ..., on_progress=callable)`; events from workers go through a `queue.Queue` and are delivered by the runner's wait loop in the calling thread.
- **Inputs**: events from worker threads.
- **Outputs**: `on_progress(event)` runs only in the thread that iterates `Runner.run`; the wait loop wakes at least every 0.2 seconds so the CLI can refresh elapsed time even without new events.
- **Behavior**: remaining queued events are drained before a final result of the same label is yielded, so a `finalizing` event never arrives after its instance's result.

### Capability: Terminal rendering
Show one live line; stay silent when it cannot work.

#### Feature: Live status line and `--quiet`
- **Description**: The CLI shows active jobs through `console.status`.
- **Inputs**: `--quiet` flag; whether stderr/stdout is a terminal (`sys.stdout.isatty()`).
- **Outputs**: a single `console.status` line updated with `Status.update`, formatted `label phase [NN%] M:SS` for each active job joined by ` | `; the percentage appears only when `done_bytes` and `total_bytes` are not `None` and `total_bytes > 0`, is `min(99, done*100//total)`, and is dropped for a `finalizing` phase. Final result lines and the summary are printed exactly as before.
- **Behavior**: with `--quiet`, or when stdout is not a terminal, or under `--dry-run` or `--plan`, no status is created and `on_progress` is `None`. `--quiet` does not hide failures, skips or the summary.

## Structural Decomposition

### Repository Structure

```
src/tools/backup/step_result.py                # Maps to: ProgressEvent
src/tools/backup/capabilities/tar_archive.py   # Maps to: Engine reporting
src/tools/backup/runner.py                     # Maps to: Delivery to the calling thread
src/tools/backup/cli.py                        # Maps to: Live status line and --quiet
tests/tools/backup/test_progress.py            # Maps to: all features
docs/source/tools/backup.rst                   # Maps to: documentation
CHANGELOG.md                                   # Maps to: documentation
```

### Module: step_result
- **Maps to capability**: Progress events
- **Responsibility**: define the event record.
- **Location**: `src/tools/backup/step_result.py`
- **Exports**: `ProgressEvent`
- New symbols: `ProgressEvent`, `progress`, `on_progress`, `quiet`, `done_bytes`, `archiving`, `finalizing`, `scanning`, `test_percent_uses_input_bytes_not_output_size`, `test_no_live_output_when_not_a_tty_or_quiet`

### Module: tar_archive
- **Maps to capability**: Progress events
- **Responsibility**: emit events from both engines.
- **Location**: `src/tools/backup/capabilities/tar_archive.py`

### Module: runner
- **Maps to capability**: Progress events
- **Responsibility**: queue and deliver events on the calling thread.
- **Location**: `src/tools/backup/runner.py`

### Module: cli
- **Maps to capability**: Terminal rendering
- **Responsibility**: `--quiet`, status line formatting.
- **Location**: `src/tools/backup/cli.py`

## Dependency Graph

### Foundation Layer (Phase 0)
- **step_result**: no dependencies; built first.

### Core Layer (Phase 1)
- **tar_archive**: Depends on [step_result]
- **runner**: Depends on [step_result]

### Integration Layer (Phase 2)
- **cli**: Depends on [runner, tar_archive]

## Implementation Phases

### Phase 0: Foundation
**Goal**: The event record exists.

**Tasks**:
- [ ] Add `ProgressEvent` to `src/tools/backup/step_result.py` (no deps) - Acceptance: `uv run pytest tests/tools/backup/test_progress.py -k event_record -q` passes.

**Exit Criteria**: `ProgressEvent` importable with four fields.

### Phase 1: Core
**Goal**: Engines emit, the runner delivers.

**Tasks**:
- [ ] Emit events from the Python writer and the system-tar path in `src/tools/backup/capabilities/tar_archive.py` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_progress.py -k "engine or input_bytes or swallowed" -q` passes.
- [ ] Add `on_progress`, the queue, the 0.2 second wake-up and drain-before-result ordering to `src/tools/backup/runner.py` (depends on: Phase 0) - Acceptance: `uv run pytest tests/tools/backup/test_progress.py -k "runner or calling_thread or drain" -q` passes.

**Exit Criteria**: events reach `on_progress` on the calling thread, in order per label.

### Phase 2: Integration
**Goal**: Operator-visible rendering and docs.

**Tasks**:
- [ ] Add `--quiet`, the status line and its formatter to `src/tools/backup/cli.py` (depends on: Phase 1) - Acceptance: `uv run pytest tests/tools/backup/test_progress.py -k "cli or quiet or format" -q` passes.
- [ ] Document progress and `--quiet` in `docs/source/tools/backup.rst`; add an `Added` line under `[Unreleased]` in `CHANGELOG.md` (depends on: Phase 1) - Acceptance: `rg -c "\-\-quiet" docs/source/tools/backup.rst CHANGELOG.md` prints a count of at least 1 for each file.

**Exit Criteria**: `uv run pytest tests/tools/backup -q` passes (including `tests/tools/backup/test_invariants.py`); `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` are clean.

## Test Strategy

### Critical Scenarios
- **Happy path**: Python engine, three files → Expected: `scanning`, `archiving` (total set), `archiving` with `done_bytes` ending at the total, `finalizing`.
- **Edge case**: system-tar engine → Expected: no percentage; phase and elapsed still shown.
- **Edge case**: empty source (`total_bytes == 0`) → Expected: no percentage, no divide by zero.
- **Edge case**: parallel jobs → Expected: all callbacks run on the main thread (assert `threading.current_thread()`).
- **Error case**: progress callback raises → Expected: archive still succeeds.
- **Error case**: `--quiet`, or stdout not a TTY → Expected: no status created; result lines and summary printed.

## Risks

- **Misleading percentage**: files that grow or vanish during the run change the total. Mitigation: percentage is capped at 99 until the result arrives and is dropped when the total is zero or unknown.
- **Event flood**: per-file events on a huge tree. Mitigation: at most one event per 0.2 seconds per archive.
- **Terminal assumptions**: the CLI is the only shipped interface (`src/tools/backup/manifest.toml`), but the runner and capabilities stay terminal-free; only `src/tools/backup/cli.py` touches the console.
