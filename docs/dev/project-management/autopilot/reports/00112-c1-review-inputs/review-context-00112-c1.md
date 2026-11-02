# Review Context

## Completed Tasks

| ID | Task | Status | Commit | Description | Shared with |
|----|------|--------|--------|-------------|-------------|
| 1 | Add ProgressEvent record | completed |  | Add ProgressEvent record  Location: /Users/bob/git/src/github.com/buvis/gems/src/tools/backup/step_result.py  Reuse: Existing NamedTuple records, archive writers, completion queue, pending-result reporting and console.status as identified in reviewed design.  Contract (verbatim — reviewed design): In `backup.step_result`:  ```python class ProgressEvent(NamedTuple):     label: str     phase: Literal["scanning", "archiving", "finalizing"]     done_bytes: int \| None     total_bytes: int \| None ```  Field order is exactly `label, phase, done_bytes, total_bytes`; there are no defaults and no new enum or base class. Byte values are nonnegative input sizes, never compressed output sizes. The immutable record can cross worker threads without sharing mutable call state.  Details: - Add focused tests to /Users/bob/git/src/github.com/buvis/gems/tests/tools/backup/test_progress.py. Preserve earlier tasks' tests. Use names matching this acceptance selector. If splitting for 800-line limit, use non-collected sibling progress_*_cases.py and import test classes into test_progress.py. - Test failure, empty/unknown values and cancellation behavior where applicable; preserve previous interfaces.  Acceptance criteria: - uv run pytest tests/tools/backup/test_progress.py -k event_record -q passes.  Verify: uv run pytest tests/tools/backup/test_progress.py -k event_record -q |  |
| 2 | Emit archive engine progress | completed |  | Emit archive engine progress  Location: /Users/bob/git/src/github.com/buvis/gems/src/tools/backup/capabilities/tar_archive.py  Reuse: Existing NamedTuple records, archive writers, completion queue, pending-result reporting and console.status as identified in reviewed design.  Contract (verbatim — reviewed design): Keep the existing protocol-compatible signature:  ```python def TarArchive.run(self: TarArchive, **kwargs: object) -> Iterator[StepResult]: ...  def _emit_progress(     progress: Callable[[ProgressEvent], None] \| None,     event: ProgressEvent, ) -> None: ...  def TarArchive._archive_result(     label: str, arcbase: Path, out: Path, walk: WalkResult, engine: str, *,     cancel: threading.Event \| None = None,     progress: Callable[[ProgressEvent], None] \| None = None, ) -> StepResult: ...  def _write_archive(     out: Path, arcbase: Path, files: Iterable[Path], *,     cancel: threading.Event \| None = None,     on_bytes: Callable[[int], None] \| None = None,     on_finalize: Callable[[], None] \| None = None, ) -> None: ...  def _write_archive_system_tar(     out: Path, arcbase: Path, files: Iterable[Path], *,     cancel: threading.Event \| None = None,     on_finalize: Callable[[], None] \| None = None, ) -> str \| None: ... ```  `TarArchive.run` accepts the runtime kwarg `progress: Callable[[ProgressEvent], None] \| None`; parse it from `kwargs`, then pass it through the existing validated-run path. Do not add it to `TarArchive.inputs`. `_emit_progress` calls a non-None callback and swallows ordinary `Exception`; it does not swallow `KeyboardInterrupt`, `SystemExit`, `GeneratorExit` or other `BaseException`. Genuine interruption must retain the established cancellation/cleanup behavior. The runner applies the same exception policy to consumer callbacks.  For a real validated run, emit `ProgressEvent(label, "scanning", None, None)` immediately before `_walk_tree` or `_select_items`. Invalid inputs, a missing source and preflight rejection do not enter a walk and need no fabricated activity. A bundle which becomes a skip during selection can end after scanning. For `dry_run=True`, disable the emitter before either walk and never call `progress`, including for direct capability use.  After a successful walk and before writing, emit `ProgressEvent(label, "archiving", 0, walk.total_bytes)` for the configured Python engine, or `ProgressEvent(label, "archiving", None, walk.total_bytes)` for the configured system-tar engine. Set the initial throttle timestamp with `time.monotonic()` at this boundary.  The Python writer calls `on_bytes(cumulative_done)` only after each successful `tar.add(..., recursive=False)`. When accounting is enabled, obtain `file_path.lstat()` immediately before adding the member; add its `st_size` only if `stat.S_ISREG(st_mode)`. Directories and all symlinks, including broken links, contribute zero and must not be followed for counting. Regular source paths that tar encodes as hardlinks still contribute their input `st_size`, consistent with `walk.total_bytes`. Keep accounting state local to this invocation; `CAPABILITIES` contains a shared singleton `TarArchive`.  `_archive_result` owns the cumulative count and event throttle. Update its latest count on every writer callback; emit intermediate archiving events only when at least `0.2` monotonic seconds have elapsed since the previous archiving event. On successful archive-stream close, flush the last count as an archiving event if it differs from the last reported count, then emit `ProgressEvent(label, "finalizing", done, walk.total_bytes)`. The unconditional final cumulative flush is the minimal resolution of the PRD's short-archive tension: intermediate updates are limited to one per 0.2 seconds, while the required final count is never omitted and archive completion is never delayed to satisfy a UI rate limit. Scanning, the initial archiving event and phase transitions are boundary events.  `on_finalize()` runs inside each writer immediately after the archive stream closes successfully and before fsync/publication: after the Python tar context exits, or after successful system-tar communication returns. It must not run for a failed stream. Existing raw-file flush, fsync, mode 0600, cancellation checks, atomic `os.replace` and `BaseException` temp cleanup remain in their current order. A finalizing event means the stream closed, not that publication succeeded; the terminal `StepResult` remains authoritative.  For the configured system-tar engine, `done_bytes` is `None` for every archiving/finalizing event. A failed system attempt followed by the existing Python fallback retains this activity-only policy for the instance: pass no `on_bytes` callback to the fallback writer, but preserve finalizing and the existing fallback note. This avoids changing percentage semantics partway through a configured system-tar job. No subprocess output parsing or archive-size polling is introduced.  Details: - Add focused tests to /Users/bob/git/src/github.com/buvis/gems/tests/tools/backup/test_progress.py. Preserve earlier tasks' tests. Use names matching this acceptance selector. If splitting for 800-line limit, use non-collected sibling progress_*_cases.py and import test classes into test_progress.py. - Test failure, empty/unknown values and cancellation behavior where applicable; preserve previous interfaces.  Acceptance criteria: - uv run pytest tests/tools/backup/test_progress.py -k "engine or input_bytes or swallowed" -q passes.  Verify: uv run pytest tests/tools/backup/test_progress.py -k "engine or input_bytes or swallowed" -q  Additional PRD acceptance criteria (verbatim): - `test_percent_uses_input_bytes_not_output_size` passes: with an incompressible and a highly compressible fixture, the reported done bytes equal the summed sizes of the files added. |  |
| 3 | Deliver runner progress on calling thread | completed |  | Deliver runner progress on calling thread  Location: /Users/bob/git/src/github.com/buvis/gems/src/tools/backup/runner.py  Reuse: Existing NamedTuple records, archive writers, completion queue, pending-result reporting and console.status as identified in reviewed design.  Contract (verbatim — reviewed design): ```python def Runner.__init__(     self: Runner, cfg: BackupConfig, *, dry_run: bool = False, jobs: int = 3,     on_progress: Callable[[ProgressEvent], None] \| None = None,     on_tick: Callable[[], None] \| None = None, ) -> None: ... ```  Keep `Runner.run`, `request_cancel`, `plan`, `interrupted` and `cancelled_names` contracts unchanged. `on_tick` is an optional, backward-compatible refinement of the PRD's wake-up requirement: a wake-up with no event needs a distinct hook to recompute elapsed text. Never replay an old `ProgressEvent`, synthesize a heartbeat phase, yield non-results or create a CLI timer thread to implement a tick.  Each `run()` creates a fresh `queue.Queue[ProgressEvent](maxsize=256)` for progress, separate from the existing completed-future queue. The progress queue holds at most 256 events. Workers receive only the enqueue callable as `progress`; they never receive `on_progress`, `on_tick` or a console object. The enqueue callable checks the run's cancellation event, then calls `put(event, timeout=0.2)`; on `queue.Full`, retry while cancellation remains unset. If cancellation becomes set, return without enqueueing or raising. A queue timeout is backpressure, never an archive failure. No event is silently dropped for an uncancelled successful instance. When `on_progress is None` or `dry_run=True`, pass `progress=None` instead. No callbacks are invoked by `plan()`. Suppress both callbacks for dry runs.  While work remains pending, drain currently queued progress with `get_nowait()` before waiting for a completion, then use `completed.get(timeout=0.2)`. Catch `queue.Empty` as a normal wake-up, drain progress again, and invoke the optional tick on the iteration thread. Drain on completion notification as well. Drain before every terminal result is yielded, including ready preflight rows and cancellation outcomes, and once after joined workers finish during normal cancellation. These drains unblock bounded-queue producers even when no future has completed. Enqueuing is synchronous inside the capability, before its future completes, so a completed uncancelled instance's entire queued progress prefix is available before its result. Preserve FIFO event order per label. Cross-label event order is queue insertion order and need not equal configured launch order. After cancellation, no new progress enqueue is required; drain every event already queued before terminal cancellation results.  Ticks run on the thread advancing `Runner.run`, only while the generator is actively executing. The wait loop offers a tick at least every 0.2 seconds during an otherwise idle wait, subject to scheduler/callback execution time; no guarantee applies while the consumer holds a yielded result or the existing blocking cancellation join runs. A callback must be short and nonblocking. Catch ordinary exceptions from each `on_progress`/`on_tick` invocation separately so one broken observer cannot turn any archive into a failure. Preserve calling-thread `KeyboardInterrupt` handling, request cancellation and drain the same run.  On generator abandonment, set cancellation before joining writers, so producers blocked on the bounded queue observe cancellation after at most their current 0.2-second put timeout and return. Do not invoke user callbacks from the abandonment-only `finally` path. Normal cancellation likewise sets cancellation before shutdown/join, then drains the joined queue before yielding results. Release per-run queue references on exit. A subsequent run uses clean queues and cannot receive earlier events. Do not refactor outcomes, submission boundaries, lost-notification recovery or cancellation ordering as part of this feature.  Details: - Add focused tests to /Users/bob/git/src/github.com/buvis/gems/tests/tools/backup/test_progress.py. Preserve earlier tasks' tests. Use names matching this acceptance selector. If splitting for 800-line limit, use non-collected sibling progress_*_cases.py and import test classes into test_progress.py. - Test failure, empty/unknown values and cancellation behavior where applicable; preserve previous interfaces.  Acceptance criteria: - uv run pytest tests/tools/backup/test_progress.py -k "runner or calling_thread or drain" -q passes.  Verify: uv run pytest tests/tools/backup/test_progress.py -k "runner or calling_thread or drain" -q |  |
| 4 | Render live progress and quiet mode | completed |  | Render live progress and quiet mode  Location: /Users/bob/git/src/github.com/buvis/gems/src/tools/backup/cli.py  Reuse: Existing NamedTuple records, archive writers, completion queue, pending-result reporting and console.status as identified in reviewed design.  Contract (verbatim — reviewed design): ```python @click.option("--quiet", is_flag=True, help="Hide live progress; keep final results and the summary.")  def _format_progress(event: ProgressEvent, elapsed: float) -> str: ...  class _LiveProgress:     def on_progress(self, event: ProgressEvent) -> None: ...     def refresh(self) -> None: ...     def finish(self, label: str) -> None: ...     def close(self) -> None: ...  def _report_steps(     steps: Iterable[StepResult], *, dry_run: bool = False,     on_interrupt: Callable[[], None] \| None = None,     on_result: Callable[[StepResult], None] \| None = None, ) -> bool: ...  def _run_plan(     cfg: BackupConfig, plan: list[tuple[str, BackupInstance]], *,     dry_run: bool, plan_only: bool, jobs: int = 3, quiet: bool = False, ) -> bool: ... ```  Add `quiet: bool` to the Click callback and forward it to `_run_plan`. Live mode is exactly `not quiet and sys.stdout.isatty() and not dry_run and not plan_only`; use stdout as the explicit functional contract specifies, even though introductory PRD wording mentions stderr/stdout. Existing list/show-excludes early returns never construct live status. In every disabled mode, construct no status and pass `on_progress=None`, `on_tick=None` to `Runner`.  `_format_progress` returns `label phase [NN%] M:SS` when both byte fields exist, `total_bytes > 0` and `phase != "finalizing"`; `NN = min(99, done_bytes * 100 // total_bytes)`. Otherwise omit the percentage and its surrounding space. Brackets are literal display characters. Elapsed seconds are `max(0, int(elapsed))`, formatted with `divmod(seconds, 60)`; minutes can exceed 59 and seconds always have two digits. Examples: `docs archiving [37%] 1:05`, `git scanning 0:02`, `git finalizing 2:00`.  `_LiveProgress` stores latest events and first-seen `time.monotonic()` timestamps by label, in first-event insertion order. Waiting/unsubmitted instances are not active. Phase changes preserve the first timestamp. `on_progress` replaces the label's latest event and refreshes; `refresh` joins active strings with `" \| "` and calls `Status.update`. Use `rich.text.Text` for the rendered string passed to `Status.update` so configured labels and literal percentage brackets cannot be parsed as Rich markup. Only CLI owns Rich imports and status objects.  Create at most one `console.status("")` object per live run, lazily at the first event, and start it only while active labels exist. Stop it when the last active label finishes; restart the same object if later submitted work emits its first event. `finish(label)` removes the label and timestamp idempotently and refreshes the remaining jobs. `close()` stops the status idempotently. No status is needed for an empty run or only preflight failures.  Call `_report_steps(..., on_result=lambda step: live.finish(step.label))` in live mode. The report loop invokes `on_result(pending)` immediately before `_report_step(pending)` inside its existing interrupt-handling boundary. Keep the pending result and counters across rendering retries; `finish` is idempotent, and each result still affects counters once. A completed/failed/skipped/cancelled label disappears before its final line prints. Keep `_report_step`, final messages, summary counts and ordinary exit codes unchanged. `--quiet` suppresses redraws only; every result, skip, failure and summary remains visible.  Use `finally` in `_run_plan` to close the original runner generator and the live status on every exit. Preserve the existing retained-iterator interrupt path and exit-130 message. Status updates interrupted by `KeyboardInterrupt` reach the runner or report-loop cancellation owner; cleanup must not leave a spinner or active writer running. Do not move execution into a UI thread.  Details: - Add focused tests to /Users/bob/git/src/github.com/buvis/gems/tests/tools/backup/test_progress.py. Preserve earlier tasks' tests. Use names matching this acceptance selector. If splitting for 800-line limit, use non-collected sibling progress_*_cases.py and import test classes into test_progress.py. - Test failure, empty/unknown values and cancellation behavior where applicable; preserve previous interfaces.  Acceptance criteria: - uv run pytest tests/tools/backup/test_progress.py -k "cli or quiet or format" -q passes.  Verify: uv run pytest tests/tools/backup/test_progress.py -k "cli or quiet or format" -q  Additional PRD acceptance criteria (verbatim): - `test_no_live_output_when_not_a_tty_or_quiet` passes: final result lines and the summary are still printed. |  |
| 5 | Document live progress and quiet | completed |  | Document live progress and quiet  Location: /Users/bob/git/src/github.com/buvis/gems/docs/source/tools/backup.rst, /Users/bob/git/src/github.com/buvis/gems/CHANGELOG.md, /Users/bob/git/src/github.com/buvis/gems/README.md  Reuse: Existing NamedTuple records, archive writers, completion queue, pending-result reporting and console.status as identified in reviewed design.  Contract (verbatim — reviewed design): Document progress and `--quiet` in `docs/source/tools/backup.rst`; add an `Added` line under `[Unreleased]` in `CHANGELOG.md`.  Details: - Include README backup section, matching project CLI documentation convention. Explain activity-only system tar, honest input-byte percentages, finalizing, elapsed receipt origin and retained final output.  Acceptance criteria: - rg -c "\-\-quiet" docs/source/tools/backup.rst CHANGELOG.md prints a count of at least 1 for each file.  Verify: rg -c "\-\-quiet" docs/source/tools/backup.rst CHANGELOG.md Documentation details: consolidate interim ProgressEvent/engine/runner/live progress Added entries into one concise user-facing --quiet/progress entry, preserving unrelated Added entries. Document TTY-only live status, input-byte percentage capped99 and no finalizing percentage, system-tar activity-only (including fallback), disabled live modes, final output preserved, elapsed starts on event receipt. Keep concise. Reading budget: README.md backup section lines110-120; docs/source/tools/backup.rst usage/parallelism lines1-65; CHANGELOG.md Unreleased/Added first30 lines. No unrelated docs edits. |  |

## Code Changes

### Changed Files
_Diff scope: incremental review (changes since 853b765e2662d64a8cc2363ac1582228bfc88d90)_

```
 CHANGELOG.md                                       |    1 +
 README.md                                          |    4 +
 .../autopilot/autocodex-metrics.jsonl              |    1 +
 .../53825f23ae4b4d71864c4deb31d3f825.jsonl         |  944 ++++++++++++++++
 .../53825f23ae4b4d71864c4deb31d3f825.prompt.md     |  280 +++++
 .../53825f23ae4b4d71864c4deb31d3f825.stderr        |  335 ++++++
 .../autopilot/dispatch-metrics.jsonl               |   81 ++
 .../autopilot/ledger/dispatch-metrics.jsonl        |   81 ++
 ...rogress-and-quiet-v1-implementation-models.json |  324 ++++++
 ...-progress-and-quiet-v1-implementation-models.md |   43 +
 .../autopilot/reports/00112-build-evidence.md      |   29 +
 .../autopilot/reports/00112-design-result.txt      |    7 +
 .../autopilot/reports/00112-design-review-2.md     |   60 +
 .../autopilot/reports/00112-native-evidence.json   |  233 ++++
 .../autopilot/reports/00112-task-1-devon.md        |  152 +++
 .../reports/00112-task-1-ivan1-session.jsonl       |   63 ++
 .../reports/00112-task-1-pat-metadata.jsonl        |    2 +
 .../autopilot/reports/00112-task-1-review.md       |   10 +
 .../reports/00112-task-1-tess1-session.jsonl       |   59 +
 .../00112-task-1-tess1_strengthen-session.jsonl    |   65 ++
 .../autopilot/reports/00112-task-2-devon-proof.md  |  432 +++++++
 .../reports/00112-task-2-ivan2-session.jsonl       |  106 ++
 .../reports/00112-task-2-ivan2_retry-session.jsonl |   65 ++
 .../reports/00112-task-2-pat-metadata.jsonl        |    2 +
 .../autopilot/reports/00112-task-2-review.md       |    9 +
 .../reports/00112-task-2-tess2-session.jsonl       |  108 ++
 .../00112-task-2-tess2_quality-session.jsonl       |   74 ++
 .../00112-task-2-tess2_strengthen-session.jsonl    |  106 ++
 .../reports/00112-task-2-tess2_style-session.jsonl |   47 +
 .../autopilot/reports/00112-task-3-devon-proof.md  | 1186 ++++++++++++++++++++
 .../reports/00112-task-3-ivan3-session.jsonl       |  123 ++
 .../reports/00112-task-3-ivan3_retry-session.jsonl |   87 ++
 .../reports/00112-task-3-pat-metadata.jsonl        |    2 +
 .../autopilot/reports/00112-task-3-review.md       |   12 +
 .../reports/00112-task-3-tess3-session.jsonl       |  200 ++++
 .../00112-task-3-tess3_quality-session.jsonl       |   90 ++
 .../00112-task-3-tess3_strengthen-session.jsonl    |  107 ++
 .../autopilot/reports/00112-task-4-devon-proof.md  |  693 ++++++++++++
 .../reports/00112-task-4-ivan4-session.jsonl       |  129 +++
 .../reports/00112-task-4-ivan4_doc-session.jsonl   |   50 +
 .../reports/00112-task-4-pat-metadata.jsonl        |    2 +
 .../autopilot/reports/00112-task-4-review.md       |    8 +
 .../reports/00112-task-4-tess4-session.jsonl       |  165 +++
 .../00112-task-4-tess4_quality-session.jsonl       |   62 +
 .../00112-task-4-tess4_strengthen-session.jsonl    |  100 ++
 .../reports/00112-task-5-ivan5-session.jsonl       |   51 +
 .../reports/00112-task-5-ivan5_retry-session.jsonl |   42 +
 .../autopilot/reports/00112-verification-final.log |  139 +++
 .../reports/00112-verification-unisolated.log      |  192 ++++
 ...112-backup-live-progress-and-quiet-v1-design.md |  218 ++++
 docs/dev/project-management/meta/assumptions.md    |   16 +-
 .../00112-backup-live-progress-and-quiet-v1.md     |    0
 docs/source/tools/backup.rst                       |   14 +
 src/tools/backup/capabilities/tar_archive.py       |  108 +-
 src/tools/backup/cli.py                            |   95 +-
 src/tools/backup/runner.py                         |   98 +-
 src/tools/backup/step_result.py                    |   11 +-
 tests/tools/backup/progress_cli_cases.py           |  539 +++++++++
 tests/tools/backup/progress_engine_cases.py        |  216 ++++
 tests/tools/backup/progress_runner_cases.py        |  550 +++++++++
 tests/tools/backup/test_progress.py                |  707 ++++++++++++
 61 files changed, 9670 insertions(+), 65 deletions(-)
```

### Diff Content
Full diff available at: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/review-diff-00112-c1.diff

(10417 lines)

## PRD Requirements

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

## Mechanical facts (computed, do not re-count)

Function line counts from `ast`. Cite these for countable claims; a
finding that contradicts this block is discarded at the review gate.

- `CHANGELOG.md` — skipped (non-python)
- `README.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/53825f23ae4b4d71864c4deb31d3f825.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/53825f23ae4b4d71864c4deb31d3f825.prompt.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/autocodex-sessions/53825f23ae4b4d71864c4deb31d3f825.stderr` — skipped (non-python)
- `docs/dev/project-management/autopilot/dispatch-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/ledger/dispatch-metrics.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-backup-live-progress-and-quiet-v1-implementation-models.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-backup-live-progress-and-quiet-v1-implementation-models.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-build-evidence.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-design-result.txt` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-design-review-2.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-native-evidence.json` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-1-devon.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-1-ivan1-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-1-pat-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-1-review.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-1-tess1-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-1-tess1_strengthen-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-devon-proof.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-ivan2-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-ivan2_retry-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-pat-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-review.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-tess2-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-tess2_quality-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-tess2_strengthen-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-2-tess2_style-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-devon-proof.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-ivan3-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-ivan3_retry-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-pat-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-review.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-tess3-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-tess3_quality-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-3-tess3_strengthen-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-devon-proof.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-ivan4-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-ivan4_doc-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-pat-metadata.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-review.md` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-tess4-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-tess4_quality-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-4-tess4_strengthen-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-5-ivan5-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-task-5-ivan5_retry-session.jsonl` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-verification-final.log` — skipped (non-python)
- `docs/dev/project-management/autopilot/reports/00112-verification-unisolated.log` — skipped (non-python)
- `docs/dev/project-management/designs/00112-backup-live-progress-and-quiet-v1-design.md` — skipped (non-python)
- `docs/dev/project-management/meta/assumptions.md` — skipped (non-python)
- `docs/dev/project-management/prds/wip/00112-backup-live-progress-and-quiet-v1.md` — skipped (non-python)
- `docs/source/tools/backup.rst` — skipped (non-python)
- `src/tools/backup/capabilities/tar_archive.py`
  - `_check_cancel` — line 37, 3 lines
  - `_emit_progress` — line 42, 4 lines
  - `_archive_callbacks` — line 48, 22 lines
  - `_archive_callbacks.on_bytes` — line 56, 7 lines
  - `_archive_callbacks.on_finalize` — line 64, 4 lines
  - `WalkResult.__init__` — line 84, 11 lines
  - `WalkResult.file_count` — line 97, 2 lines
  - `TarArchive.inputs` — line 114, 2 lines
  - `TarArchive.plan` — line 117, 36 lines
  - `TarArchive.run` — line 154, 30 lines
  - `TarArchive._run_validated` — line 185, 45 lines
  - `TarArchive._dry_run_result` — line 232, 12 lines
  - `TarArchive._archive_result` — line 246, 30 lines
  - `_reject_out_inside_source` — line 278, 20 lines
  - `_normalize_items` — line 300, 16 lines
  - `_select_items` — line 318, 38 lines
  - `_walk_tree` — line 358, 70 lines
  - `_raise_walk_error` — line 430, 8 lines
  - `_collect_applied` — line 440, 8 lines
  - `_write_archive` — line 450, 42 lines
  - `_write_archive_system_tar` — line 494, 49 lines
  - `_run_system_tar` — line 545, 32 lines
  - `_cleanup_tar_process` — line 579, 17 lines
  - `_parse_inputs` — line 598, 9 lines
  - `_missing_input` — line 609, 5 lines
  - `_resolve_paths` — line 616, 9 lines
  - `_require_str` — line 627, 3 lines
  - `_expand_stamp` — line 632, 10 lines
  - `_as_str_tuple` — line 644, 4 lines
- `src/tools/backup/cli.py`
  - `_format_progress` — line 24, 11 lines
  - `_LiveProgress.__init__` — line 38, 5 lines
  - `_LiveProgress.on_progress` — line 44, 5 lines
  - `_LiveProgress.refresh` — line 50, 14 lines
  - `_LiveProgress.finish` — line 65, 4 lines
  - `_LiveProgress.close` — line 70, 4 lines
  - `_report_step` — line 76, 8 lines
  - `_report_steps` — line 86, 45 lines
  - `_parse_only` — line 133, 5 lines
  - `_describe` — line 140, 3 lines
  - `_apply_overrides` — line 145, 13 lines
  - `_override_selected` — line 160, 12 lines
  - `_list_instances` — line 174, 6 lines
  - `_load_config` — line 182, 17 lines
  - `_show_excludes` — line 201, 50 lines
  - `_select_plan` — line 253, 31 lines
  - `_run_plan` — line 286, 49 lines
  - `cli` — line 356, 49 lines
- `src/tools/backup/runner.py`
  - `_enqueue_progress` — line 29, 7 lines
  - `Runner.__init__` — line 47, 21 lines
  - `Runner.request_cancel` — line 69, 5 lines
  - `Runner.run` — line 75, 28 lines
  - `Runner._execute` — line 104, 48 lines
  - `Runner._drain_progress` — line 153, 9 lines
  - `Runner._collect_completion` — line 163, 19 lines
  - `Runner._cancel_remaining` — line 183, 13 lines
  - `Runner._shutdown` — line 197, 7 lines
  - `Runner._cancelled_result` — line 205, 4 lines
  - `Runner.plan` — line 210, 2 lines
  - `Runner._plan` — line 213, 41 lines
  - `Runner._run_instance` — line 255, 32 lines
- `src/tools/backup/step_result.py`
  - `StepResult.__init__` — line 43, 14 lines
  - `StepResult.out_path` — line 59, 2 lines
  - `StepResult.file_count` — line 63, 2 lines
  - `StepResult.total_bytes` — line 67, 2 lines
- `tests/tools/backup/progress_cli_cases.py`
  - `StatusRecorder.__init__` — line 23, 6 lines
  - `StatusRecorder.status` — line 30, 3 lines
  - `StatusRecorder.start` — line 34, 3 lines
  - `StatusRecorder.stop` — line 38, 3 lines
  - `StatusRecorder.update` — line 42, 7 lines
  - `cli_display` — line 52, 7 lines
  - `ControlledCapability.__init__` — line 64, 4 lines
  - `ControlledCapability.plan` — line 69, 3 lines
  - `ControlledCapability.run` — line 73, 10 lines
  - `controlled_plan` — line 85, 10 lines
  - `result_lines` — line 97, 6 lines
  - `TestCliProgressFormat.test_format_uses_input_byte_floor_caps_and_unbounded_minutes` — line 123, 7 lines
  - `TestCliProgressFormat.test_format_percentage_handles_varied_byte_ratios` — line 135, 3 lines
  - `TestCliLiveProgress.test_cli_three_active_labels_preserve_order_and_elapsed_across_phase_changes` — line 141, 20 lines
  - `TestCliLiveProgress.test_cli_status_preserves_first_seen_time_order_and_exact_labels` — line 162, 34 lines
  - `TestCliLiveProgress.test_cli_real_rich_status_restarts_after_all_labels_finish` — line 197, 27 lines
  - `TestCliLiveProgress.test_cli_real_rich_status_restarts_after_all_labels_finish.capture_status` — line 206, 4 lines
  - `TestCliLiveProgress.test_cli_interrupted_status_update_propagates_and_close_stops_spinner` — line 225, 15 lines
  - `TestCliProgressRunPlan.test_cli_report_summary_counts_each_outcome_and_describes_dry_run` — line 244, 9 lines
  - `TestCliProgressRunPlan.test_cli_result_output_uses_the_outcome_severity` — line 262, 12 lines
  - `TestCliProgressRunPlan.test_cli_skipped_success_keeps_success_exit_and_skip_count` — line 275, 8 lines
  - `TestCliProgressRunPlan.test_cli_live_runner_tick_refreshes_elapsed_without_new_progress` — line 284, 27 lines
  - `TestCliProgressRunPlan.test_cli_live_runner_tick_refreshes_elapsed_without_new_progress.initialize` — line 296, 9 lines
  - `TestCliProgressRunPlan.test_cli_quiet_and_early_returns_never_create_live_status` — line 313, 43 lines
  - `TestCliProgressRunPlan.test_cli_report_retries_pending_result_after_interrupt_without_duplicate_counts` — line 357, 29 lines
  - `TestCliProgressRunPlan.test_cli_report_retries_pending_result_after_interrupt_without_duplicate_counts.before_result` — line 370, 4 lines
  - `TestCliProgressRunPlan.test_cli_result_callback_error_is_surfaced_before_printing_result` — line 387, 12 lines
  - `TestCliProgressRunPlan.test_cli_result_callback_error_is_surfaced_before_printing_result.fail_render` — line 393, 2 lines
  - `TestCliProgressRunPlan.test_cli_interrupted_live_run_closes_capability_and_status_before_exit_130` — line 400, 16 lines
  - `TestCliProgressRunPlan.test_no_live_output_when_not_a_tty_or_quiet` — line 418, 23 lines
  - `TestCliProgressRunPlan.test_cli_disabled_modes_pass_no_progress_or_tick_callbacks_to_real_runner` — line 451, 41 lines
  - `TestCliProgressRunPlan.test_cli_disabled_modes_pass_no_progress_or_tick_callbacks_to_real_runner.initialize` — line 471, 3 lines
  - `TestCliProgressRunPlan.test_cli_live_run_removes_completed_labels_before_each_final_line` — line 493, 28 lines
  - `TestCliProgressRunPlan.test_cli_live_run_removes_completed_labels_before_each_final_line.observe_output` — line 504, 5 lines
  - `TestCliProgressRunPlan.test_cli_live_run_without_active_events_never_creates_status` — line 523, 17 lines
- `tests/tools/backup/progress_engine_cases.py`
  - `TestStrengthenedEngineProgress.test_input_bytes_uses_member_size_before_add_changes_source` — line 17, 21 lines
  - `TestStrengthenedEngineProgress.test_input_bytes_uses_member_size_before_add_changes_source.add_then_change` — line 24, 3 lines
  - `TestStrengthenedEngineProgress.test_engine_scanning_is_delivered_before_selection_or_tree_walk` — line 40, 29 lines
  - `TestStrengthenedEngineProgress.test_engine_scanning_is_delivered_before_selection_or_tree_walk.walk_after_scanning` — line 51, 3 lines
  - `TestStrengthenedEngineProgress.test_input_bytes_failed_stream_close_never_finalizes_or_publishes` — line 70, 22 lines
  - `TestStrengthenedEngineProgress.test_input_bytes_failed_stream_close_never_finalizes_or_publishes.fail_close` — line 77, 5 lines
  - `TestStrengthenedEngineProgress.test_engine_syncs_closed_archive_before_atomic_publication` — line 94, 33 lines
  - `TestStrengthenedEngineProgress.test_engine_syncs_closed_archive_before_atomic_publication.sync` — line 105, 3 lines
  - `TestStrengthenedEngineProgress.test_engine_syncs_closed_archive_before_atomic_publication.publish` — line 109, 3 lines
  - `TestStrengthenedEngineProgress.test_engine_syncs_closed_archive_before_atomic_publication.progress` — line 113, 4 lines
  - `TestStrengthenedEngineProgress.test_engine_cancellation_without_callback_exception_preserves_output_and_cleans_temp` — line 128, 21 lines
  - `TestStrengthenedEngineProgress.test_engine_cancellation_without_callback_exception_preserves_output_and_cleans_temp.cancel_after_member` — line 140, 3 lines
  - `TestStrengthenedEngineProgress.test_engine_system_tar_completes_subprocess_without_python_fallback` — line 150, 36 lines
  - `TestStrengthenedEngineProgress.test_engine_system_tar_completes_subprocess_without_python_fallback.launch` — line 160, 4 lines
  - `TestStrengthenedEngineProgress.test_engine_system_tar_completes_subprocess_without_python_fallback.open_without_python_writer` — line 165, 3 lines
  - `TestStrengthenedEngineProgress.test_engine_system_finalizing_interruption_is_not_swallowed_or_published` — line 188, 29 lines
  - `TestStrengthenedEngineProgress.test_engine_system_finalizing_interruption_is_not_swallowed_or_published.interrupt_finalizing` — line 198, 4 lines
- `tests/tools/backup/progress_runner_cases.py`
  - `_frames` — line 19, 6 lines
  - `_Capability.__init__` — line 30, 4 lines
  - `_Capability.plan` — line 35, 4 lines
  - `_Capability.run` — line 40, 3 lines
  - `_config` — line 45, 6 lines
  - `_outcomes` — line 53, 2 lines
  - `_blocking_waits` — line 57, 11 lines
  - `_blocking_waits.get` — line 61, 4 lines
  - `_OrderedCapability.__init__` — line 71, 6 lines
  - `_OrderedCapability.produce_ordered` — line 78, 11 lines
  - `TestRunnerCallingThread.test_runner_honors_requested_worker_concurrency` — line 93, 26 lines
  - `TestRunnerCallingThread.test_runner_honors_requested_worker_concurrency.produce` — line 98, 4 lines
  - `TestRunnerCallingThread.test_runner_forwards_inputs_effective_exclusions_and_one_runtime_timestamp` — line 127, 36 lines
  - `TestRunnerCallingThread.test_runner_preserves_every_result_from_each_capability` — line 164, 21 lines
  - `TestRunnerCallingThread.test_runner_preserves_every_result_from_each_capability.produce` — line 167, 6 lines
  - `TestRunnerCallingThread.test_runner_preserves_fifo_events_and_drains_before_results_on_calling_thread` — line 188, 37 lines
  - `TestRunnerCallingThread.test_runner_preserves_fifo_events_and_drains_before_results_on_calling_thread.observe` — line 197, 3 lines
  - `TestRunnerCallingThread.test_runner_preserves_fifo_events_and_drains_before_results_on_calling_thread.consume` — line 205, 7 lines
  - `TestRunnerCallingThread.test_runner_ticks_without_events_and_isolates_each_observer_exception` — line 227, 48 lines
  - `TestRunnerCallingThread.test_runner_ticks_without_events_and_isolates_each_observer_exception.produce` — line 237, 6 lines
  - `TestRunnerCallingThread.test_runner_ticks_without_events_and_isolates_each_observer_exception.tick` — line 244, 5 lines
  - `TestRunnerCallingThread.test_runner_ticks_without_events_and_isolates_each_observer_exception.observe` — line 250, 3 lines
  - `TestRunnerSuppression.test_runner_passes_no_progress_for_dry_run_or_absent_observer` — line 279, 28 lines
  - `TestRunnerSuppression.test_runner_passes_no_progress_for_dry_run_or_absent_observer.produce` — line 288, 4 lines
  - `TestRunnerSuppression.test_runner_plan_and_empty_configuration_never_invoke_callbacks` — line 308, 21 lines
  - `TestRunnerSuppression.test_runner_unknown_capability_yields_failure_without_fabricated_progress` — line 330, 25 lines
  - `TestRunnerSuppression.test_runner_unknown_capability_yields_failure_without_fabricated_progress.produce` — line 336, 4 lines
  - `TestRunnerCancellation.test_runner_drains_queued_prefix_when_observer_requests_cancel_or_interrupts` — line 359, 41 lines
  - `TestRunnerCancellation.test_runner_drains_queued_prefix_when_observer_requests_cancel_or_interrupts.produce` — line 368, 10 lines
  - `TestRunnerCancellation.test_runner_drains_queued_prefix_when_observer_requests_cancel_or_interrupts.observe` — line 379, 7 lines
  - `TestRunnerCancellation.test_runner_uses_fresh_progress_queue_for_each_run` — line 401, 24 lines
  - `TestRunnerCancellation.test_runner_uses_fresh_progress_queue_for_each_run.produce` — line 408, 6 lines
  - `_FloodCapability.__init__` — line 428, 10 lines
  - `_FloodCapability.produce_flood` — line 439, 21 lines
  - `_suspend_flood` — line 462, 17 lines
  - `_assert_queue_backpressure` — line 481, 6 lines
  - `TestRunnerBoundedQueue.test_runner_drains_full_queue_without_waiting_for_a_completed_future` — line 490, 16 lines
  - `TestRunnerBoundedQueue.test_runner_cancel_unblocks_backpressure_and_drains_every_previously_queued_event` — line 507, 17 lines
  - `TestRunnerBoundedQueue.test_runner_abandonment_cancels_before_join_and_never_calls_observers_in_finally` — line 525, 26 lines
  - `TestRunnerBoundedQueue.test_runner_abandonment_cancels_before_join_and_never_calls_observers_in_finally.rescue_blocked_close` — line 533, 4 lines
- `tests/tools/backup/test_progress.py`
  - `TestProgressEventRecord.test_event_record_has_exact_named_tuple_fields_types_and_no_defaults` — line 48, 10 lines
  - `TestProgressEventRecord.test_event_record_preserves_each_positional_field_and_byte_value` — line 71, 24 lines
  - `TestProgressEventRecord.test_event_record_rejects_field_mutation` — line 97, 6 lines
  - `TestProgressEventRecord.test_event_record_requires_all_four_arguments` — line 108, 3 lines
  - `TestProgressEventRecord.test_event_record_distinguishes_similar_labels_and_each_field` — line 112, 6 lines
  - `TestProgressEventRecord.test_event_record_crosses_worker_thread_without_sharing_mutable_call_state` — line 119, 37 lines
  - `TestProgressEventRecord.test_event_record_crosses_worker_thread_without_sharing_mutable_call_state.update_in_worker` — line 122, 4 lines
  - `_create_selected_input_source` — line 158, 7 lines
  - `TestArchiveEngineProgress.test_engine_reports_ordered_phases_and_selected_input_bytes_before_publication` — line 170, 49 lines
  - `TestArchiveEngineProgress.test_engine_reports_ordered_phases_and_selected_input_bytes_before_publication.progress` — line 183, 4 lines
  - `TestArchiveEngineProgress.test_engine_throttles_at_two_tenths_and_flushes_short_final_count` — line 221, 43 lines
  - `TestArchiveEngineProgress.test_engine_throttles_at_two_tenths_and_flushes_short_final_count.add_with_clock` — line 236, 3 lines
  - `TestArchiveEngineProgress.test_engine_short_archive_flushes_without_waiting_or_duplicate_final_count` — line 266, 30 lines
  - `TestArchiveEngineProgress.test_engine_direct_dry_run_never_calls_progress` — line 299, 29 lines
  - `TestArchiveEngineProgress.test_engine_unwalkable_source_emits_no_fabricated_activity` — line 330, 25 lines
  - `TestArchiveEngineProgress.test_engine_selection_skip_can_end_after_scanning` — line 356, 23 lines
  - `TestArchiveEngineProgress.test_engine_unavailable_system_tar_falls_back_with_activity_only_progress` — line 380, 38 lines
  - `TestArchiveEngineProgress.test_engine_empty_source_reports_zero_total_and_finalizes_real_archive` — line 420, 30 lines
  - `TestArchiveInputBytes.test_percent_uses_input_bytes_not_output_size` — line 454, 44 lines
  - `TestArchiveInputBytes.test_input_bytes_counts_regular_paths_and_hardlinks_but_not_directories_or_symlinks` — line 500, 34 lines
  - `TestArchiveInputBytes.test_input_bytes_empty_writer_finalizes_without_member_callbacks` — line 535, 9 lines
  - `TestArchiveInputBytes.test_input_bytes_failed_member_preserves_output_and_never_finalizes` — line 546, 36 lines
  - `TestArchiveInputBytes.test_input_bytes_failed_member_preserves_output_and_never_finalizes.fail_second` — line 564, 4 lines
  - `TestArchiveInputBytes.test_input_bytes_state_is_local_to_each_shared_capability_run` — line 583, 28 lines
  - `TestProgressExceptionsSwallowed.test_ordinary_progress_exception_is_swallowed_after_delivering_exact_event` — line 624, 12 lines
  - `TestProgressExceptionsSwallowed.test_ordinary_progress_exception_is_swallowed_after_delivering_exact_event.callback` — line 628, 3 lines
  - `TestProgressExceptionsSwallowed.test_base_exception_is_not_swallowed_by_progress_emitter` — line 638, 12 lines
  - `TestProgressExceptionsSwallowed.test_base_exception_is_not_swallowed_by_progress_emitter.callback` — line 642, 3 lines
  - `TestProgressExceptionsSwallowed.test_callback_exception_is_swallowed_and_real_engine_archive_finishes` — line 652, 29 lines
  - `TestProgressExceptionsSwallowed.test_callback_exception_is_swallowed_and_real_engine_archive_finishes.callback` — line 660, 4 lines
  - `TestProgressExceptionsSwallowed.test_engine_interrupt_is_not_swallowed_and_writer_cleans_temporary_archive` — line 683, 25 lines
  - `TestProgressExceptionsSwallowed.test_engine_interrupt_is_not_swallowed_and_writer_cleans_temporary_archive.callback` — line 697, 4 lines

## Tautological test shapes (computed, do not re-judge)

Each `[MECH]` line is a test whose shape cannot fail as written. Raise
it; step 6 adds any line the table lacks. `mech-check` is the finder.


Checked 23 test function(s) in 1 test file(s).

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `853b765e2662`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.


Replay: 0 touched test(s) ran, 0 failed against base, 0 passed; 1 test file(s) could not be collected at base (their tests fail there). Command: uv run pytest

## Context Pack

Pack file: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-review-inputs/engram-pack-00112-c1.md

### Findings precedent

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  - F4: read `MACHINE_PATH` (`checks.py:89-92`). The `/` branch requires at least one `segment/`, so `/tmp` and `/config.json` never match, and `$HOME` has no branch.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00005-behavior-rules-review-01.md
  - F1: each of the three guard tests seeds a defect in the same file after its no-finding assertion. Mutation at `ba8e7b8`: with `closed_fences`, `portable_links` and `requirement_source` returning `[]`, all three tests fail.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00007-reviews-and-conversion-review-01.md
  - F7: accepted (ledger entry added). The T-077 outcome records the copy as a choice: each scan runs standalone by `python3 <path>`.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  # Review: 00012-autopilot-package-contract-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-01.md
  autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/tmp/blake-output-ap00012-c1.txt.receipt.json

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  The source's Codex-only inline-input requirement is adapted to the authorized Claude transport: Bob received the complete assembled persona, rubrics and appendices plus readable context/diff paths. His successful raw tool reads establish that the restriction that motivated inline-only Codex prompts does not apply. The 45 MB full diff was not truncated into a prompt. No implementation thread was resumed.

- findings:/Users/bob/git/src/github.com/buvis/agent-plugins/docs/dev/project-management/reviews/00012-autopilot-package-contract-v1-review-02.md
  Provider: Anthropic; served model claude-opus-5-5; effort xhigh; session 95ff83bd-845a-4d23-9d77-2b8ff0ab183b.

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00009-walk-memory-proposal-queue-v1-review-1.md
  # Review: 00009-walk-memory-proposal-queue-v1

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00051-qwen-eval-harness-core-v1-review-1.md
  ### Classification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00051-qwen-eval-harness-core-v1-review-2.md
  ### Adversarial verification

- findings:/Users/bob/git/src/github.com/buvis/agent-skills/docs/dev/project-management/reviews/00058-page-links-accept-javascript-urls-v1-review-1.md
  Fact-Forcing Gate (`gateguard`) — `error=Command blocked by PreToolUse hook:

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00176-guard-the-target-reads-in-the-doctor-v1-review-03.md
  ```

- findings:/Users/bob/git/src/github.com/buvis/claude-autopilot/docs/dev/project-management/reviews/00182-close-open-dispatch-rows-at-session-handoffs-v1-review-2.md
  `5ebd59c`, `6273c54`, `9d6bdef`, `5a5daa8`, `a026540`. Cycle 1 reviewed the full

## Test gate

Tests: 6372 passed, 0 failed, 16 skipped (suite run this cycle)
