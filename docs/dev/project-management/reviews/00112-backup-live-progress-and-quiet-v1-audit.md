# Decision Audit Log: 00112-backup-live-progress-and-quiet-v1

PRD: `00112-backup-live-progress-and-quiet-v1.md`
Started: 2026-11-01T22:52:50Z
Completed: 2026-11-01T22:52:50Z
Autonomous: 20  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: Progress design contracts

**Choice**: Use reviewed bounded queue, caller-thread tick and final cumulative flush

**Rationale**: Two independent design reviews; no open blockers; nonblocking concerns retained in design log; four-field event retained

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: Full test process inherited agent identity and portfolio configuration

**Choice**: Reuse unchanged existing00111 verification isolation runner after reproducing3 failures and passing3 targeted isolated cases

**Rationale**: Same environment-only failures documented in prior PRD; all tests retained, no HOME/product/test changes

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: In the system-tar path, `on_finalize()` runs before fsync/chmod/`os.replace`. An `OSError` there returns a fallback reason, the Python writer then re-archives the whole tree and emits a second `finalizing`. No `archiving` event is re-emitted, so the status shows "finalizing" for the entire fallback write. This is a rare edge case, but the phase is misleading while it lasts

**Choice**: tail sweep

**Rationale**: Confirmed same on_finalize callback survives post-close system-tar OSError and Python fallback; re-emit activity-only archiving without moving stream-close boundary.

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: `_archive_callbacks` is named like a pure factory, but calling it emits the initial `archiving` event and starts the throttle clock. It also returns `on_finalize` even when `progress is None`, while `on_bytes` is gated. Rename it to state the side effect (e.g. `_start_archive_progress`) or emit the boundary event explicitly in `_archive_result`

**Choice**: tail sweep

**Rationale**: Both implementation-aware reviewers identify the hidden boundary emission; mechanical helper rename preserves callback/throttle behavior.

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: `from queue import Queue as ProgressQueue` sits next to `import queue` with no comment. It exists only so tests that monkeypatch `backup.runner.queue.Queue` (test_runner_interrupt_boundaries.py:77, test_parallel_runner.py:782) don't also replace the progress queue. A cleanup to `queue.Queue` would silently move those injections onto the progress drain. Add a one-line comment

**Choice**: tail sweep

**Rationale**: Two reviewers confirm distinct Queue binding protects existing completion-queue monkeypatch seam; add explanatory comment.

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: The new public contracts are not documented in code. `Runner.__init__` `on_progress`/`on_tick` lack a docstring covering calling-thread delivery, ordinary exceptions swallowed, suppression under dry-run, and short/nonblocking callbacks. That docstring is what the "TUI/API observer" next change depends on. The `ProgressEvent` docstring omits that byte fields are input bytes and None when not measurable (PRD wording)

**Choice**: tail sweep

**Rationale**: Two reviewers confirm missing caller-thread, suppression and short/nonblocking observer documentation; add bounded contract documentation.

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: The diff deletes documented rationale from two writer docstrings outside the feature's scope. `_write_archive` lost the explanation of why it does its own mkstemp+fsync+`os.replace` instead of `pybase.filesystem.atomic_write` (a large tarball must stream, not be built in memory), which is the recorded exception to the AGENTS.md atomic-persistence invariant. `_write_archive_system_tar` lost the security rationale (`--no-recursion` keeps excluded content out; NUL delimiting stops newline-filename member injection) and its Google `Returns:` section. Its new two-line docstring also has no blank line after the summary. Build evidence shows trimming was used to hold the 49-line bound. Restore the text, and if the cap binds, extract the fsync/chmod/replace publication block into a helper

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: `_write_archive` binds `size` inside one `if on_bytes is not None:` block and reads it in a second identical block after `tar.add`, so `size` is conditionally bound. Simpler: a `_input_size(path) -> int` helper (lstat, `st_size` if `S_ISREG` else 0), with `size = _input_size(file_path) if on_bytes is not None else 0` before the add and one guarded `done += size; on_bytes(done)` after it

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: No test pins the post-join drain in the cancellation branch. Every cancellation test has already queued its events before the drain at the top of the loop, so deleting this drain would leave the suite green. If that happens, an event whose put completes while workers are joining arrives after its label's cancellation result, and the label reappears in the live status.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: The `self._on_progress is not None and not self._dry_run` guard in `_drain_progress` is half redundant. `_execute` passes `progress=None` under those conditions, so the queue is never filled. Only the None check (needed for mypy) is required

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: Several tests in the new progress suite re-test unchanged PRD 00111 behavior and would pass at base if collected: `test_runner_forwards_inputs_effective_exclusions_and_one_runtime_timestamp`, `test_cli_report_summary_counts_each_outcome_and_describes_dry_run`, `test_cli_result_output_uses_the_outcome_severity`, `test_cli_skipped_success_keeps_success_exit_and_skip_count`. They overlap test_backup_cli.py and test_plan_runner.py. The class name `TestStrengthenedEngineProgress` names the workflow step, not what it tests

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: The PRD gives `Runner.__init__` one new kwarg, `on_progress`, and lists no new exports. The implementation also adds `on_tick`, which the CLI uses to refresh elapsed time when no events arrive. The PRD requires that refresh but names no way to do it, so this is a PRD gap closed with an unlisted parameter.

**Choice**: discard

**Rationale**: single-voice; reviewed design explicitly defines optional on_tick to satisfy the PRD idle elapsed refresh

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: The final catch-up `archiving` event in `on_finalize` ignores the 0.2 second throttle. Two further `archiving` events can therefore arrive less than 0.2 seconds apart; a test asserts a 0.1999 second gap. The spec text says at most one per 0.2 seconds, but the PRD happy path requires `done_bytes` to end at the total. The excess is at most one event per archive.

**Choice**: discard

**Rationale**: single-voice; reviewed design explicitly requires final cumulative flush to retain final input bytes

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: The progress queue is bounded (`maxsize=256`) and `_enqueue_progress` blocks until a slot frees. The PRD names only a plain `queue.Queue` and says progress can never fail an archive. A blocked put does not fail the archive, but it can stall the writer. This happens when the consumer holds a yielded result and does not iterate, for example when TTY output is paused with Ctrl-S.

**Choice**: discard

**Rationale**: single-voice; reviewed design specifies bounded cancellation-aware backpressure and excludes consumer-held yields from tick timing

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: A failure inside `on_result` (`_LiveProgress.finish` → `refresh`) propagates out of `_report_steps`. That closes the runner generator, which cancels in-flight archives, and the user sees a raw traceback. The runner swallows the same `refresh` failure when it comes through `on_tick`, and progress_cli_cases.py:387 pins the propagation.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: Cannot statically verify: on a real 80-column TTY, the joined status for three or more active jobs updates in place, does not leave stale wrapped lines, and clears before each result line and the summary.

**Choice**: discard

**Rationale**: single-voice; no exact runnable project verification command; manual real-TTY directions are not queued

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: In the system-tar path, `on_finalize()` runs before fsync/chmod/`os.replace`. An `OSError` there returns a fallback reason, the Python writer then re-archives the whole tree and emits a second `finalizing`. No `archiving` event is re-emitted, so the status shows "finalizing" for the entire fallback write. This is a rare edge case, but the phase is misleading while it lasts

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: `_archive_callbacks` is named like a pure factory, but calling it emits the initial `archiving` event and starts the throttle clock. It also returns `on_finalize` even when `progress is None`, while `on_bytes` is gated. Rename it to state the side effect (e.g. `_start_archive_progress`) or emit the boundary event explicitly in `_archive_result`

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: `from queue import Queue as ProgressQueue` sits next to `import queue` with no comment. It exists only so tests that monkeypatch `backup.runner.queue.Queue` (test_runner_interrupt_boundaries.py:77, test_parallel_runner.py:782) don't also replace the progress queue. A cleanup to `queue.Queue` would silently move those injections onto the progress drain. Add a one-line comment

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-01T22:52:50Z

**Decision**: The new public contracts are not documented in code. `Runner.__init__` `on_progress`/`on_tick` lack a docstring covering calling-thread delivery, ordinary exceptions swallowed, suppression under dry-run, and short/nonblocking callbacks. That docstring is what the "TUI/API observer" next change depends on. The `ProgressEvent` docstring omits that byte fields are input bytes and None when not measurable (PRD wording)

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [deferred] 2026-11-01T22:52:50Z

**Decision**: Pre-existing Ruff E501 in immutable00105 verification report script line22

**Choice**: Defer historical evidence formatting; product lint scope src/tests/tools is clean

**Rationale**: Unchanged at work_start853b765e, outside current backup progress scope; raw historical audit must remain intact
