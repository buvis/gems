---
catchup: skip
design: run
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
- **Exports**: none new; `TarArchive.run` gains the `progress` kwarg.

### Module: runner
- **Maps to capability**: Progress events
- **Responsibility**: queue and deliver events on the calling thread.
- **Location**: `src/tools/backup/runner.py`
- **Exports**: none new; `Runner.__init__` gains the `on_progress` kwarg.

### Module: cli
- **Maps to capability**: Terminal rendering
- **Responsibility**: `--quiet`, status line formatting.
- **Location**: `src/tools/backup/cli.py`
- **Exports**: none new.

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

## Design Doc

# backup: live progress and --quiet — design

## Architecture fit

Extend the existing capability → threaded `Runner` → CLI path. Archive selection and byte accounting remain in `src/tools/backup/capabilities/tar_archive.py`; queue delivery belongs to `runner.py`; terminal eligibility, elapsed time and Rich status ownership belong to `cli.py`. `step_result.py` supplies an interface-neutral event alongside its existing records. No new dependencies, cross-tool imports, persistence, config keys or shipped interfaces are needed.

Context: root `AGENTS.md`, `docs/dev/project-management/meta/project-capsule.md`, the PRD and its source discovery were read. No nested `AGENTS.md` exists under `docs/`, `src/` or `tests/`; the optional cartographer atlas directory is absent. Preserve PRD 00111's bounded submissions, completion-order results, cancellation, generator cleanup and exit 130. Preserve all existing archive selection, skip and atomic-publication behavior. The capability protocol already accepts runtime `**kwargs: object`; `progress` is runtime context, not an accepted YAML `with:` input.

The event has the PRD's four fields: label, phase, done bytes and total bytes. Two refinements are explicit below: a separate optional caller-thread `on_tick` hook enables elapsed refresh without inventing progress events, and the final cumulative byte flush is a boundary notification exempt from intermediate update throttling.

## Module placement

| Path | Change |
| --- | --- |
| `src/tools/backup/step_result.py` | Edit: add `ProgressEvent`, leaving `StepResult`, `ArchiveMeta` and `PlanEntry` unchanged. |
| `src/tools/backup/capabilities/tar_archive.py` | Edit: safe event delivery, phase boundaries, Python input-byte accounting and two optional internal writer callbacks. |
| `src/tools/backup/runner.py` | Edit: optional progress/tick callbacks, per-run progress queue, timed completion waits and drain-before-result delivery. |
| `src/tools/backup/cli.py` | Edit: `--quiet`, formatter, one private live-status owner and lifecycle integration with existing result reporting. |
| `tests/tools/backup/test_progress.py` | New: class-organized engine, runner, formatting and CLI behavior tests. |
| `tests/tools/backup/test_runner_interrupt_boundaries.py`, `tests/tools/backup/test_parallel_runner.py` | Edit only if queue-injection seams need to distinguish progress from completion queues; preserve each existing regression scenario. |
| `docs/source/tools/backup.rst`, `CHANGELOG.md` | Edit: progress/quiet behavior and an Added entry under Unreleased. |
| `README.md` | Edit: concise progress/`--quiet` addition to the existing backup section, as required by the project capsule's CLI documentation convention. |

## Interfaces & contracts

### Event record

In `backup.step_result`:

```python
class ProgressEvent(NamedTuple):
    label: str
    phase: Literal["scanning", "archiving", "finalizing"]
    done_bytes: int | None
    total_bytes: int | None
```

Field order is exactly `label, phase, done_bytes, total_bytes`; there are no defaults and no new enum or base class. Byte values are nonnegative input sizes, never compressed output sizes. The immutable record can cross worker threads without sharing mutable call state.

### Capability and writer hooks

Keep the existing protocol-compatible signature:

```python
def TarArchive.run(self: TarArchive, **kwargs: object) -> Iterator[StepResult]: ...

def _emit_progress(
    progress: Callable[[ProgressEvent], None] | None,
    event: ProgressEvent,
) -> None: ...

def TarArchive._archive_result(
    label: str, arcbase: Path, out: Path, walk: WalkResult, engine: str, *,
    cancel: threading.Event | None = None,
    progress: Callable[[ProgressEvent], None] | None = None,
) -> StepResult: ...

def _write_archive(
    out: Path, arcbase: Path, files: Iterable[Path], *,
    cancel: threading.Event | None = None,
    on_bytes: Callable[[int], None] | None = None,
    on_finalize: Callable[[], None] | None = None,
) -> None: ...

def _write_archive_system_tar(
    out: Path, arcbase: Path, files: Iterable[Path], *,
    cancel: threading.Event | None = None,
    on_finalize: Callable[[], None] | None = None,
) -> str | None: ...
```

`TarArchive.run` accepts the runtime kwarg `progress: Callable[[ProgressEvent], None] | None`; parse it from `kwargs`, then pass it through the existing validated-run path. Do not add it to `TarArchive.inputs`. `_emit_progress` calls a non-None callback and swallows ordinary `Exception`; it does not swallow `KeyboardInterrupt`, `SystemExit`, `GeneratorExit` or other `BaseException`. Genuine interruption must retain the established cancellation/cleanup behavior. The runner applies the same exception policy to consumer callbacks.

For a real validated run, emit `ProgressEvent(label, "scanning", None, None)` immediately before `_walk_tree` or `_select_items`. Invalid inputs, a missing source and preflight rejection do not enter a walk and need no fabricated activity. A bundle which becomes a skip during selection can end after scanning. For `dry_run=True`, disable the emitter before either walk and never call `progress`, including for direct capability use.

After a successful walk and before writing, emit `ProgressEvent(label, "archiving", 0, walk.total_bytes)` for the configured Python engine, or `ProgressEvent(label, "archiving", None, walk.total_bytes)` for the configured system-tar engine. Set the initial throttle timestamp with `time.monotonic()` at this boundary.

The Python writer calls `on_bytes(cumulative_done)` only after each successful `tar.add(..., recursive=False)`. When accounting is enabled, obtain `file_path.lstat()` immediately before adding the member; add its `st_size` only if `stat.S_ISREG(st_mode)`. Directories and all symlinks, including broken links, contribute zero and must not be followed for counting. Regular source paths that tar encodes as hardlinks still contribute their input `st_size`, consistent with `walk.total_bytes`. Keep accounting state local to this invocation; `CAPABILITIES` contains a shared singleton `TarArchive`.

`_archive_result` owns the cumulative count and event throttle. Update its latest count on every writer callback; emit intermediate archiving events only when at least `0.2` monotonic seconds have elapsed since the previous archiving event. On successful archive-stream close, flush the last count as an archiving event if it differs from the last reported count, then emit `ProgressEvent(label, "finalizing", done, walk.total_bytes)`. The unconditional final cumulative flush is the minimal resolution of the PRD's short-archive tension: intermediate updates are limited to one per 0.2 seconds, while the required final count is never omitted and archive completion is never delayed to satisfy a UI rate limit. Scanning, the initial archiving event and phase transitions are boundary events.

`on_finalize()` runs inside each writer immediately after the archive stream closes successfully and before fsync/publication: after the Python tar context exits, or after successful system-tar communication returns. It must not run for a failed stream. Existing raw-file flush, fsync, mode 0600, cancellation checks, atomic `os.replace` and `BaseException` temp cleanup remain in their current order. A finalizing event means the stream closed, not that publication succeeded; the terminal `StepResult` remains authoritative.

For the configured system-tar engine, `done_bytes` is `None` for every archiving/finalizing event. A failed system attempt followed by the existing Python fallback retains this activity-only policy for the instance: pass no `on_bytes` callback to the fallback writer, but preserve finalizing and the existing fallback note. This avoids changing percentage semantics partway through a configured system-tar job. No subprocess output parsing or archive-size polling is introduced.

### Runner delivery and tick

```python
def Runner.__init__(
    self: Runner, cfg: BackupConfig, *, dry_run: bool = False, jobs: int = 3,
    on_progress: Callable[[ProgressEvent], None] | None = None,
    on_tick: Callable[[], None] | None = None,
) -> None: ...
```

Keep `Runner.run`, `request_cancel`, `plan`, `interrupted` and `cancelled_names` contracts unchanged. `on_tick` is an optional, backward-compatible refinement of the PRD's wake-up requirement: a wake-up with no event needs a distinct hook to recompute elapsed text. Never replay an old `ProgressEvent`, synthesize a heartbeat phase, yield non-results or create a CLI timer thread to implement a tick.

Each `run()` creates a fresh `queue.Queue[ProgressEvent](maxsize=256)` for progress, separate from the existing completed-future queue. The progress queue holds at most 256 events. Workers receive only the enqueue callable as `progress`; they never receive `on_progress`, `on_tick` or a console object. The enqueue callable checks the run's cancellation event, then calls `put(event, timeout=0.2)`; on `queue.Full`, retry while cancellation remains unset. If cancellation becomes set, return without enqueueing or raising. A queue timeout is backpressure, never an archive failure. No event is silently dropped for an uncancelled successful instance. When `on_progress is None` or `dry_run=True`, pass `progress=None` instead. No callbacks are invoked by `plan()`. Suppress both callbacks for dry runs.

While work remains pending, drain currently queued progress with `get_nowait()` before waiting for a completion, then use `completed.get(timeout=0.2)`. Catch `queue.Empty` as a normal wake-up, drain progress again, and invoke the optional tick on the iteration thread. Drain on completion notification as well. Drain before every terminal result is yielded, including ready preflight rows and cancellation outcomes, and once after joined workers finish during normal cancellation. These drains unblock bounded-queue producers even when no future has completed. Enqueuing is synchronous inside the capability, before its future completes, so a completed uncancelled instance's entire queued progress prefix is available before its result. Preserve FIFO event order per label. Cross-label event order is queue insertion order and need not equal configured launch order. After cancellation, no new progress enqueue is required; drain every event already queued before terminal cancellation results.

Ticks run on the thread advancing `Runner.run`, only while the generator is actively executing. The wait loop offers a tick at least every 0.2 seconds during an otherwise idle wait, subject to scheduler/callback execution time; no guarantee applies while the consumer holds a yielded result or the existing blocking cancellation join runs. A callback must be short and nonblocking. Catch ordinary exceptions from each `on_progress`/`on_tick` invocation separately so one broken observer cannot turn any archive into a failure. Preserve calling-thread `KeyboardInterrupt` handling, request cancellation and drain the same run.

On generator abandonment, set cancellation before joining writers, so producers blocked on the bounded queue observe cancellation after at most their current 0.2-second put timeout and return. Do not invoke user callbacks from the abandonment-only `finally` path. Normal cancellation likewise sets cancellation before shutdown/join, then drains the joined queue before yielding results. Release per-run queue references on exit. A subsequent run uses clean queues and cannot receive earlier events. Do not refactor outcomes, submission boundaries, lost-notification recovery or cancellation ordering as part of this feature.

### CLI rendering and lifecycle

```python
@click.option("--quiet", is_flag=True, help="Hide live progress; keep final results and the summary.")

def _format_progress(event: ProgressEvent, elapsed: float) -> str: ...

class _LiveProgress:
    def on_progress(self, event: ProgressEvent) -> None: ...
    def refresh(self) -> None: ...
    def finish(self, label: str) -> None: ...
    def close(self) -> None: ...

def _report_steps(
    steps: Iterable[StepResult], *, dry_run: bool = False,
    on_interrupt: Callable[[], None] | None = None,
    on_result: Callable[[StepResult], None] | None = None,
) -> bool: ...

def _run_plan(
    cfg: BackupConfig, plan: list[tuple[str, BackupInstance]], *,
    dry_run: bool, plan_only: bool, jobs: int = 3, quiet: bool = False,
) -> bool: ...
```

Add `quiet: bool` to the Click callback and forward it to `_run_plan`. Live mode is exactly `not quiet and sys.stdout.isatty() and not dry_run and not plan_only`; use stdout as the explicit functional contract specifies, even though introductory PRD wording mentions stderr/stdout. Existing list/show-excludes early returns never construct live status. In every disabled mode, construct no status and pass `on_progress=None`, `on_tick=None` to `Runner`.

`_format_progress` returns `label phase [NN%] M:SS` when both byte fields exist, `total_bytes > 0` and `phase != "finalizing"`; `NN = min(99, done_bytes * 100 // total_bytes)`. Otherwise omit the percentage and its surrounding space. Brackets are literal display characters. Elapsed seconds are `max(0, int(elapsed))`, formatted with `divmod(seconds, 60)`; minutes can exceed 59 and seconds always have two digits. Examples: `docs archiving [37%] 1:05`, `git scanning 0:02`, `git finalizing 2:00`.

`_LiveProgress` stores latest events and first-seen `time.monotonic()` timestamps by label, in first-event insertion order. Waiting/unsubmitted instances are not active. Phase changes preserve the first timestamp. `on_progress` replaces the label's latest event and refreshes; `refresh` joins active strings with `" | "` and calls `Status.update`. Use `rich.text.Text` for the rendered string passed to `Status.update` so configured labels and literal percentage brackets cannot be parsed as Rich markup. Only CLI owns Rich imports and status objects.

Create at most one `console.status("")` object per live run, lazily at the first event, and start it only while active labels exist. Stop it when the last active label finishes; restart the same object if later submitted work emits its first event. `finish(label)` removes the label and timestamp idempotently and refreshes the remaining jobs. `close()` stops the status idempotently. No status is needed for an empty run or only preflight failures.

Call `_report_steps(..., on_result=lambda step: live.finish(step.label))` in live mode. The report loop invokes `on_result(pending)` immediately before `_report_step(pending)` inside its existing interrupt-handling boundary. Keep the pending result and counters across rendering retries; `finish` is idempotent, and each result still affects counters once. A completed/failed/skipped/cancelled label disappears before its final line prints. Keep `_report_step`, final messages, summary counts and ordinary exit codes unchanged. `--quiet` suppresses redraws only; every result, skip, failure and summary remains visible.

Use `finally` in `_run_plan` to close the original runner generator and the live status on every exit. Preserve the existing retained-iterator interrupt path and exit-130 message. Status updates interrupted by `KeyboardInterrupt` reach the runner or report-loop cancellation owner; cleanup must not leave a spinner or active writer running. Do not move execution into a UI thread.

## Data flow

1. CLI selects instances and checks terminal/live eligibility; disabled modes use no observer callbacks.
2. Runner performs the existing duplicate-aware preflight and bounded scheduling. Each worker gets an enqueue hook into the 256-event progress queue and the existing cancellation event; timed puts apply cancellation-aware backpressure.
3. Capability emits scanning, selects members once, emits the measured-total archiving boundary and enters the existing writer.
4. Python writer reports cumulative successful regular-file input sizes; the capability throttles intermediate events. Both writers signal successful stream close, which produces finalizing before durable publication.
5. Runner's timed completion wait drains worker events and ticks on the calling thread. CLI updates its single active-job status there.
6. Before a result is yielded, all already-queued progress is delivered. The report loop removes that label, renders its unchanged result and eventually prints the unchanged summary.
7. Cancellation uses the current shutdown/join path, then drains queued events before reporting outcomes. Every exit closes the status and generator.

## Reuse inventory

Sweep followed `~/.claude/rules-library/rationalizations.md`: verbs `emit/notify/callback`, `format/render/serialize`, `update/refresh`, `run/wait/drain`, `write/add`; nouns `progress/event/phase/percent/bytes`, `status/elapsed/duration`, `queue/thread/complete`. `rg` covered backup, pybase, sysup, pinger and bim's doc progress module. Known `Runner`, `Status`, `console.status`, `queue.Queue`, `tar.add` and `os.replace` hits verified search operation. A no-hit elapsed/formatter search was checked against known console `format_success` and backup `StepResult` hits before concluding there is no same-contract helper.

- `src/tools/backup/step_result.py:ArchiveMeta`, `PlanEntry`: follow existing `NamedTuple` records; keep terminal results distinct from transient events.
- `src/tools/backup/capabilities/tar_archive.py:WalkResult`, `_walk_tree`, `_select_items`: use the existing filtered member list and regular-file `total_bytes`; never rescan to estimate totals.
- `src/tools/backup/capabilities/tar_archive.py:_write_archive`, `_write_archive_system_tar`: add callbacks at existing member/stream-close boundaries while retaining temp/fsync/replace and cleanup ownership.
- `src/tools/backup/capabilities/tar_archive.py:_run_system_tar`: retain existing cancellable subprocess communication and 0.2-second process polling; this is not the calling-thread refresh mechanism.
- `src/tools/backup/runner.py:Runner._execute`, `_run_instance`, `_shutdown`: retain completion queue, bounded submissions, isolated runtime kwargs, callback-on-future completion and cancellation outcome recovery; add progress delivery beside them.
- `src/tools/backup/cli.py:_report_steps`, `_report_step`, `_run_plan`: extend the existing pending-result/counter/interrupt lifecycle, rather than creating another result reporter.
- `src/lib/buvis/pybase/adapters/console/console.py:ConsoleAdapter.status`: use this existing Rich Status factory; its `Status.update` accepts a `Text` renderable without changing the adapter's `status(message: str)` signature.
- `src/tools/bim/commands/doc/shared/progress.py:SpinnerProgressReporter`: reference for CLI-owned status lifetime and observer separation. Do not import across tools: its single-stage, terminal-only protocol lacks labels, byte totals, threaded queues and per-job removal.
- `tests/tools/backup/parallel_runner_helpers.py` and `test_runner_interrupt_boundaries.py`: reuse barrier/event-based worker control and cancellation-boundary regression patterns.
- Nothing found for a reusable backup progress queue/byte event/elapsed formatter; greps tried `ProgressEvent|on_progress|on_tick|progress|percent|elapsed|duration|monotonic|divmod|:02d` and `format|render|serialize|update|refresh|emit|notify|callback` in the paths above. Implement the small formatter and live state in their sole consumer, backup CLI.

## Alternatives considered

1. **Smallest diff: call `on_progress` directly inside the archive worker and update the status there.** Avoids queue/wake-up changes but violates the required calling-thread observer contract and couples worker lifetime to terminal mutation. Rejected.
2. **Chosen: a bounded 256-event progress queue beside the existing completion queue, cancellation-aware timed puts, timed completion waits and one optional tick hook.** Preserves the proven completion/cancellation implementation, bounds observer memory and permits honest activity-only status during long member writes/system tar. The extra hook resolves elapsed refresh without altering event meaning.
3. **One mixed queue containing future completions and progress, or a generic progress-reporter framework.** A mixed queue can reduce polling latency but changes completion dequeue/recovery invariants that PRD 00111 tests explicitly protect. A generic reporter adds protocols/adapters before another consumer needs them. Neither buys needed v1 behavior over a bounded 0.2-second wait.

## Risks & edge cases

- A file can grow, shrink or change type between selection, accounting and tar's own metadata/read operations. The denominator is the selected snapshot; the numerator is the sum of regular-path sizes immediately before successful adds. Stable sources end at the total. Changing sources can differ; never replace the numerator with the total merely to show completion. Percent stays capped at 99 and disappears during finalization; real metadata/read failures remain failures.
- Per-member accounting provides no byte increments within one huge `tar.add`; elapsed ticks still advance, while the percentage holds at its last completed member. This is the PRD's file-add granularity, not a promise of streaming read throughput.
- The final cumulative archiving notification can follow an intermediate notification by less than 0.2 seconds. This explicit boundary-flush refinement satisfies the PRD's required ending count on short archives without adding sleeps. Tests must distinguish intermediate throttling from boundary delivery.
- `Exception` from observers is ignored; cancellation-class `BaseException` is not. Slow callbacks can delay the calling thread. No callback isolation thread, timeout or persistent telemetry queue is added.
- The progress queue is bounded to 256 events. A paused consumer can backpressure workers; resuming iteration drains before completion waits and results. Timed puts retry without dropping uncancelled events, and cancellation releases blocked producers so shutdown and generator close do not depend on a future drain. Intermediate engine throttling remains unchanged; queue waits do not manufacture additional events or fail archives.
- Existing executor shutdown can block while a member completes; this feature does not promise ticks during that join or change direct-child system-tar supervision. Preserve the already-recorded descendant-pipe and multi-result capability limitations from PRD 00111.
- Queue monkeypatch tests currently target every `backup.runner.queue.Queue`. A second queue must not accidentally move a regression injection onto a progress drain; adapt the injection seam narrowly while preserving the original assertions.
- First-seen event receipt is the available elapsed-time origin; it excludes queue delay and waiting for a worker slot. No start timestamp is added to the four-field event. Nonterminal/quiet paths do not pay for per-member byte accounting callbacks.
- Likely next change: a TUI/API observer can use `on_progress` directly without Rich or terminal detection. Keep terminal state confined to CLI.
- Likely next change: finer-grained progress/cancellation during large-file reads can extend writer callbacks without changing the public event record. Avoid a compressed-output proxy that would constrain that extension.
- Likely next change: queue coalescing or more capabilities may need a bounded observer policy. Preserve phase/result ordering if replacing the queue later; do not expose queue objects as public API now.

## Test strategy outline

Use fake monotonic time for rate/format assertions and events/barriers for concurrent delivery. Do not assert wall-clock speed or depend on actual sleeps for event order. New tests live in `tests/tools/backup/test_progress.py`, with exact PRD-discoverable names and relevant `engine`, `runner`, `calling_thread`, `drain`, `quiet`, `cli` and `format` substrings.

- `test_event_record`: import the four-field NamedTuple, assert exact field names/order, tuple behavior and unknown-byte values.
- `test_percent_uses_input_bytes_not_output_size`: archive stable incompressible and highly compressible files, assert emitted cumulative done ends at the sum of regular-file sizes and differs from compressed output sizes. Include directory, symlink and hardlink members to check accounting semantics and member preservation.
- Python engine sequence: scanning before selection, archiving with filtered total, monotonic cumulative successful-file bytes, final cumulative flush, finalizing after gzip stream close but before publication. Fake time verifies intermediate updates never occur less than 0.2 seconds apart and tests explicitly cover the short-archive final-flush exception.
- Empty/zero-byte source and all-excluded/bundle-skip tests: no division by zero, no percentage for zero/unknown totals, no invented finalizing after skipped/failed selection. Verify missing-item and exclude behavior remains intact.
- System engine/fallback tests: scanning, activity-only archiving, finalizing on successful stream close, no output-size percentage; Python fallback preserves activity-only policy and existing note. Exercise a controlled subprocess fake plus existing real-engine coverage.
- `test_progress_callback_exception_is_swallowed`: callbacks raising ordinary exceptions at all phases leave successful archives valid and do not corrupt prior outputs. Direct dry-run capability calls invoke no callback. A cancellation-class exception retains cleanup/cancellation behavior.
- Runner tests: capture the thread advancing the generator (also use a non-main consumer thread), prove all progress/tick callbacks occur there for jobs 1 and multiple jobs, and workers only enqueue. Block workers between events, prove ticks occur through timed waits without fabricated progress. Assert per-label FIFO and finalizing-before-result, including two simultaneous completions, failed jobs, preflight rejection and cancellation after shutdown joins. Observer exceptions must not suppress other results or later observers. Reusing a runner must deliver no stale events.
- Bounded-queue tests: fill all 256 slots with a paused consumer, prove the next producer uses timed backpressure, resume and assert every uncancelled event arrives in order before its result. Cancel or close the generator while a producer is blocked and assert it returns, joins and leaves no worker alive; cancellation drains already-enqueued events before results without requiring dropped post-cancellation events. Use controlled queue fakes/events rather than real-time timeout assertions.
- Keep cancellation, lost completion notification, interrupted submission, consumer interruption, generator-close cleanup and completion-order tests from PRD 00111. Exercise interruption from the new progress/tick callbacks and check no writer/status leak or duplicate terminal result.
- Formatter tests: literal labels/brackets, unknown totals, zero totals, over-total bytes capped at 99, finalizing without percentage, elapsed 0/59/60/3600 and three joined active labels. Verify phase updates retain the timestamp and results remove only their own label.
- `test_no_live_output_when_not_a_tty_or_quiet`: parameterize stdout TTY/quiet plus dry-run/plan/list/show-excludes; spy on `console.status` and Runner callbacks. Assert disabled modes create no status and use no progress/tick callback, while final results/skips/failures/summary retain previous text and exit codes.
- Live CLI tests: mock stdout TTY, drive fake events/ticks/results, assert one status factory call, `Status.update` receives literal `Text`, completed labels disappear before final result rendering, the same status can restart for a later job, and cleanup runs after success/failure/interruption. Cover Ctrl-C during result rendering and summary to preserve pending-result counts and exit 130.

Required gates: `uv run pytest tests/tools/backup/test_progress.py -q`; the PRD's phase-specific `-k` subsets; `uv run pytest tests/tools/backup -q` including invariants; `uv run ruff check src/tools/backup tests/tools/backup`; `uv run mypy src/tools/backup`; and `rg -c "\-\-quiet" docs/source/tools/backup.rst CHANGELOG.md`. Record the runtime used and distinguish pre-existing held Python 3.14 metadata-mocking failures from regressions. No implementation tests run during drafting. Unresolved questions: none requiring user input; the tick seam, final-flush boundary and system-fallback activity policy are explicit design refinements for review.

## Review log

Dispatch 1 actual host identity: native `gpt-6.1-sol/high`; the pinned workflow source token is `claude`.

- Resolved cardinal sin — `## Interfaces & contracts` / Runner previously specified an unbounded progress queue. It now has fixed `maxsize=256`, cancellation-aware timed puts and caller-thread drains before waits/results; the test strategy covers backpressure, lossless uncancelled delivery and cancellation of blocked producers.
- Question — `## Architecture fit` and event/test prose miscounted the four-field record. Corrected the factual miscount so all prose agrees with `label, phase, done_bytes, total_bytes`; no PRD arithmetic correction is claimed.
- Non-blocker — `## Interfaces & contracts` exempts the final cumulative byte flush from the intermediate 0.2-second throttle. Retained as an explicit design refinement resolving short-archive final-count delivery; the PRD remains unchanged.

dispatch 1 (claude): cardinal-sin 1, blocker 0, non-blocker 1, question 1

dispatch 2 (codex): cardinal-sin 0, blocker 0, non-blocker 7, question 1
Host transport: use-sonnet; requested Sonnet/high; source codex label retained for pinned schema only. Full findings: ../autopilot/reports/00112-design-review-2.md. Non-blockers recorded without design expansion: bounded backpressure stalls slow consumers; tick seam versus Rich renderer; console stream assumptions; real Status restart coverage; elapsed receipt origin; cancellation event incompleteness; completion recovery seam. Question: repeated labels/phases. All are nonblocking per reviewer; final result remains authoritative.
