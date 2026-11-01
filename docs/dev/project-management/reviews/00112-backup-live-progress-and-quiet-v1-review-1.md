---
prd: docs/dev/project-management/prds/wip/00112-backup-live-progress-and-quiet-v1.md
review: 1
date: 2026-11-01
head_sha: d13b8c8dbe9c57e708890c540ccd559d17b90dec
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: d4473e2a
  carl: 004d36e9
---

# Review: 00112-backup-live-progress-and-quiet-v1

Diff range: `853b765e2662d64a8cc2363ac1582228bfc88d90..d13b8c8dbe9c57e708890c540ccd559d17b90dec`

codex_rung_guard: not fired
provider_review_guard: satisfied
autocodex_alice_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-alice-anthropic.txt.receipt.json
autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-blake-anthropic.txt.receipt.json
autocodex_bob_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00112-c1-bob-anthropic.txt.receipt.json

Model-provider independence supersedes the legacy implementor-label guard. Eve did not run. All three lenses served Claude Opus 5.5/xhigh through Kiro; immutable receipts retain model, effort, session and hashes. No implementation thread was resumed.

Carl: unavailable, helper exit 3: refusing nested dispatch (already inside a CLI agent). No backend ran; guard preserved.

Reviewed five completed tasks. The fresh full-suite gate passed. The mechanical shape check found no findings; fail-first replay could not collect the new ProgressEvent test module against the pre-change code.

Consolidation: model-side correction of the successful script output. The script missed Alice’s first finding because leading prose shared its line, and merged Blake’s throttle finding into the unrelated factory-name issue. All 19 raw observations are retained below and map to 14 distinct findings. Consensus counts distinct reviewers per defect.

Transport: the full 12.1 MB diff exceeded Kiro’s 10 MB read limit. Both implementation-aware reviewers read the complete changed production/test files and recovered access to the 115 KB product diff using the same backend. Full diff and raw failed reads remain intact; no policy denial occurred. Bob received the complete assembled persona, consensus and D1-D5 rubrics, de-slop appendix, context and diff access under the host’s authorized read-tool transport. Blake received PRD and test-gate inputs only.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | ⚪ | In the system-tar path, `on_finalize()` runs before fsync/chmod/`os.replace`. An `OSError` there returns a fallback reason, the Python writer then re-archives the whole tree and emits a second `finalizing`. No `archiving` event is re-emitted, so the status shows "finalizing" for the entire fallback write. This is a rare edge case, but the phase is misleading while it lasts | src/tools/backup/capabilities/tar_archive.py:522 | 2 | ALICE, BLAKE, BOB |
| R2 | [2/3] | 🟡 | `_archive_callbacks` is named like a pure factory, but calling it emits the initial `archiving` event and starts the throttle clock. It also returns `on_finalize` even when `progress is None`, while `on_bytes` is gated. Rename it to state the side effect (e.g. `_start_archive_progress`) or emit the boundary event explicitly in `_archive_result` | src/tools/backup/capabilities/tar_archive.py:48 | 2 | ALICE, BOB |
| R3 | [2/3] | ⚪ | `from queue import Queue as ProgressQueue` sits next to `import queue` with no comment. It exists only so tests that monkeypatch `backup.runner.queue.Queue` (test_runner_interrupt_boundaries.py:77, test_parallel_runner.py:782) don't also replace the progress queue. A cleanup to `queue.Queue` would silently move those injections onto the progress drain. Add a one-line comment | src/tools/backup/runner.py:11 | 3 | ALICE, BOB |
| R4 | [2/3] | ⚪ | The new public contracts are not documented in code. `Runner.__init__` `on_progress`/`on_tick` lack a docstring covering calling-thread delivery, ordinary exceptions swallowed, suppression under dry-run, and short/nonblocking callbacks. That docstring is what the "TUI/API observer" next change depends on. The `ProgressEvent` docstring omits that byte fields are input bytes and None when not measurable (PRD wording) | src/tools/backup/runner.py:47 | general | ALICE, BOB |
| R5 | [1/3] | 🟡 | The diff deletes documented rationale from two writer docstrings outside the feature's scope. `_write_archive` lost the explanation of why it does its own mkstemp+fsync+`os.replace` instead of `pybase.filesystem.atomic_write` (a large tarball must stream, not be built in memory), which is the recorded exception to the AGENTS.md atomic-persistence invariant. `_write_archive_system_tar` lost the security rationale (`--no-recursion` keeps excluded content out; NUL delimiting stops newline-filename member injection) and its Google `Returns:` section. Its new two-line docstring also has no blank line after the summary. Build evidence shows trimming was used to hold the 49-line bound. Restore the text, and if the cap binds, extract the fsync/chmod/replace publication block into a helper | src/tools/backup/capabilities/tar_archive.py:459 | 2 | ALICE |
| R6 | [1/3] | 🟡 | `_write_archive` binds `size` inside one `if on_bytes is not None:` block and reads it in a second identical block after `tar.add`, so `size` is conditionally bound. Simpler: a `_input_size(path) -> int` helper (lstat, `st_size` if `S_ISREG` else 0), with `size = _input_size(file_path) if on_bytes is not None else 0` before the add and one guarded `done += size; on_bytes(done)` after it | src/tools/backup/capabilities/tar_archive.py:474 | 2 | ALICE |
| R7 | [1/3] | 🟡 | No test pins the post-join drain in the cancellation branch. Every cancellation test has already queued its events before the drain at the top of the loop, so deleting this drain would leave the suite green. If that happens, an event whose put completes while workers are joining arrives after its label's cancellation result, and the label reappears in the live status. | src/tools/backup/runner.py:128 | 3 | BOB |
| R8 | [1/3] | ⚪ | The `self._on_progress is not None and not self._dry_run` guard in `_drain_progress` is half redundant. `_execute` passes `progress=None` under those conditions, so the queue is never filled. Only the None check (needed for mypy) is required | src/tools/backup/runner.py:159 | 3 | ALICE |
| R9 | [1/3] | ⚪ | Several tests in the new progress suite re-test unchanged PRD 00111 behavior and would pass at base if collected: `test_runner_forwards_inputs_effective_exclusions_and_one_runtime_timestamp`, `test_cli_report_summary_counts_each_outcome_and_describes_dry_run`, `test_cli_result_output_uses_the_outcome_severity`, `test_cli_skipped_success_keeps_success_exit_and_skip_count`. They overlap test_backup_cli.py and test_plan_runner.py. The class name `TestStrengthenedEngineProgress` names the workflow step, not what it tests | tests/tools/backup/progress_runner_cases.py:127 | 4 | ALICE |
| R10 | [1/3] | ⚪ | The PRD gives `Runner.__init__` one new kwarg, `on_progress`, and lists no new exports. The implementation also adds `on_tick`, which the CLI uses to refresh elapsed time when no events arrive. The PRD requires that refresh but names no way to do it, so this is a PRD gap closed with an unlisted parameter. | src/tools/backup/runner.py:54 | general | BLAKE |
| R11 | [1/3] | ⚪ | The final catch-up `archiving` event in `on_finalize` ignores the 0.2 second throttle. Two further `archiving` events can therefore arrive less than 0.2 seconds apart; a test asserts a 0.1999 second gap. The spec text says at most one per 0.2 seconds, but the PRD happy path requires `done_bytes` to end at the total. The excess is at most one event per archive. | src/tools/backup/capabilities/tar_archive.py:65 | general | BLAKE |
| R12 | [1/3] | ⚪ | The progress queue is bounded (`maxsize=256`) and `_enqueue_progress` blocks until a slot frees. The PRD names only a plain `queue.Queue` and says progress can never fail an archive. A blocked put does not fail the archive, but it can stall the writer. This happens when the consumer holds a yielded result and does not iterate, for example when TTY output is paused with Ctrl-S. | src/tools/backup/runner.py:81 | general | BLAKE |
| R13 | [1/3] | ⚪ | A failure inside `on_result` (`_LiveProgress.finish` → `refresh`) propagates out of `_report_steps`. That closes the runner generator, which cancels in-flight archives, and the user sees a raw traceback. The runner swallows the same `refresh` failure when it comes through `on_tick`, and progress_cli_cases.py:387 pins the propagation. | src/tools/backup/cli.py:106 | 4 | BOB |
| R14 | [1/3] | ⚪ | Cannot statically verify: on a real 80-column TTY, the joined status for three or more active jobs updates in place, does not leave stale wrapped lines, and clears before each result line and the summary. | N/A | 4 | BOB |

## Alice

Provider: Anthropic; model Claude Opus 5.5; effort xhigh; transport Kiro.

### Anthropic

There's a smaller product diff. Reading it.[ALICE] 🟡 The diff deletes documented rationale from two writer docstrings outside the feature's scope. `_write_archive` lost the explanation of why it does its own mkstemp+fsync+`os.replace` instead of `pybase.filesystem.atomic_write` (a large tarball must stream, not be built in memory), which is the recorded exception to the AGENTS.md atomic-persistence invariant. `_write_archive_system_tar` lost the security rationale (`--no-recursion` keeps excluded content out; NUL delimiting stops newline-filename member injection) and its Google `Returns:` section. Its new two-line docstring also has no blank line after the summary. Build evidence shows trimming was used to hold the 49-line bound. Restore the text, and if the cap binds, extract the fsync/chmod/replace publication block into a helper | File: src/tools/backup/capabilities/tar_archive.py:459 | Task: 2
[ALICE] 🟡 `_write_archive` binds `size` inside one `if on_bytes is not None:` block and reads it in a second identical block after `tar.add`, so `size` is conditionally bound. Simpler: a `_input_size(path) -> int` helper (lstat, `st_size` if `S_ISREG` else 0), with `size = _input_size(file_path) if on_bytes is not None else 0` before the add and one guarded `done += size; on_bytes(done)` after it | File: src/tools/backup/capabilities/tar_archive.py:474 | Task: 2
[ALICE] 🟡 `_archive_callbacks` is named like a pure factory, but calling it emits the initial `archiving` event and starts the throttle clock. It also returns `on_finalize` even when `progress is None`, while `on_bytes` is gated. Rename it to state the side effect (e.g. `_start_archive_progress`) or emit the boundary event explicitly in `_archive_result` | File: src/tools/backup/capabilities/tar_archive.py:48 | Task: 2
[ALICE] ⚪ `from queue import Queue as ProgressQueue` sits next to `import queue` with no comment. It exists only so tests that monkeypatch `backup.runner.queue.Queue` (test_runner_interrupt_boundaries.py:77, test_parallel_runner.py:782) don't also replace the progress queue. A cleanup to `queue.Queue` would silently move those injections onto the progress drain. Add a one-line comment | File: src/tools/backup/runner.py:11 | Task: 3
[ALICE] ⚪ The `self._on_progress is not None and not self._dry_run` guard in `_drain_progress` is half redundant. `_execute` passes `progress=None` under those conditions, so the queue is never filled. Only the None check (needed for mypy) is required | File: src/tools/backup/runner.py:159 | Task: 3
[ALICE] ⚪ In the system-tar path, `on_finalize()` runs before fsync/chmod/`os.replace`. An `OSError` there returns a fallback reason, the Python writer then re-archives the whole tree and emits a second `finalizing`. No `archiving` event is re-emitted, so the status shows "finalizing" for the entire fallback write. This is a rare edge case, but the phase is misleading while it lasts | File: src/tools/backup/capabilities/tar_archive.py:522 | Task: 2
[ALICE] ⚪ The new public contracts are not documented in code. `Runner.__init__` `on_progress`/`on_tick` lack a docstring covering calling-thread delivery, ordinary exceptions swallowed, suppression under dry-run, and short/nonblocking callbacks. That docstring is what the "TUI/API observer" next change depends on. The `ProgressEvent` docstring omits that byte fields are input bytes and None when not measurable (PRD wording) | File: src/tools/backup/runner.py:47 | Task: general
[ALICE] ⚪ Several tests in the new progress suite re-test unchanged PRD 00111 behavior and would pass at base if collected: `test_runner_forwards_inputs_effective_exclusions_and_one_runtime_timestamp`, `test_cli_report_summary_counts_each_outcome_and_describes_dry_run`, `test_cli_result_output_uses_the_outcome_severity`, `test_cli_skipped_success_keeps_success_exit_and_skip_count`. They overlap test_backup_cli.py and test_plan_runner.py. The class name `TestStrengthenedEngineProgress` names the workflow step, not what it tests | File: tests/tools/backup/progress_runner_cases.py:127 | Task: 4

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Provider: Anthropic; model Claude Opus 5.5; effort xhigh; transport Kiro.

### Anthropic

[BLAKE] ⚪ The PRD gives `Runner.__init__` one new kwarg, `on_progress`, and lists no new exports. The implementation also adds `on_tick`, which the CLI uses to refresh elapsed time when no events arrive. The PRD requires that refresh but names no way to do it, so this is a PRD gap closed with an unlisted parameter. | File: src/tools/backup/runner.py:54 | Task: general

[BLAKE] ⚪ The system-tar engine can emit `finalizing` twice. `_write_archive_system_tar` emits `finalizing` before it fsyncs, chmods and replaces the temp file. If any of those steps raises `OSError`, the error is returned as a fallback reason, and `_archive_result` reruns the whole archive with the Python engine using the same `on_finalize`. The events become scanning, archiving, finalizing, finalizing, and the status line reads "finalizing" for the entire rerun. The note then says "system-tar unavailable" although tar ran successfully. | File: src/tools/backup/capabilities/tar_archive.py:535 | Task: general

[BLAKE] ⚪ The final catch-up `archiving` event in `on_finalize` ignores the 0.2 second throttle. Two further `archiving` events can therefore arrive less than 0.2 seconds apart; a test asserts a 0.1999 second gap. The spec text says at most one per 0.2 seconds, but the PRD happy path requires `done_bytes` to end at the total. The excess is at most one event per archive. | File: src/tools/backup/capabilities/tar_archive.py:65 | Task: general

[BLAKE] ⚪ The progress queue is bounded (`maxsize=256`) and `_enqueue_progress` blocks until a slot frees. The PRD names only a plain `queue.Queue` and says progress can never fail an archive. A blocked put does not fail the archive, but it can stall the writer. This happens when the consumer holds a yielded result and does not iterate, for example when TTY output is paused with Ctrl-S. | File: src/tools/backup/runner.py:81 | Task: general

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: fail
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Provider: Anthropic; model Claude Opus 5.5; effort xhigh; transport Kiro.

### Anthropic

[BOB] 🟡 No test pins the post-join drain in the cancellation branch. Every cancellation test has already queued its events before the drain at the top of the loop, so deleting this drain would leave the suite green. If that happens, an event whose put completes while workers are joining arrives after its label's cancellation result, and the label reappears in the live status. | File: src/tools/backup/runner.py:128 | Task: 3

[BOB] 🟡 `_archive_callbacks` reads like a pure factory at its call site (`on_bytes, on_finalize = _archive_callbacks(...)`, tar_archive.py:258). It also emits the initial `archiving` boundary event and starts the 0.2 s throttle clock, and its name hides both. | File: src/tools/backup/capabilities/tar_archive.py:48 | Task: 2

[BOB] ⚪ A failure inside `on_result` (`_LiveProgress.finish` → `refresh`) propagates out of `_report_steps`. That closes the runner generator, which cancels in-flight archives, and the user sees a raw traceback. The runner swallows the same `refresh` failure when it comes through `on_tick`, and progress_cli_cases.py:387 pins the propagation. | File: src/tools/backup/cli.py:106 | Task: 4

[BOB] ⚪ `from queue import Queue as ProgressQueue` sits next to `import queue` with no comment. The alias is a deliberate seam: it keeps the progress queue off the `backup.runner.queue.Queue` monkeypatch used by test_runner_interrupt_boundaries.py:77 and test_parallel_runner.py:782. A cleanup back to `queue.Queue(maxsize=256)` would silently move those injections onto progress drains. | File: src/tools/backup/runner.py:11 | Task: 3

[BOB] ⚪ The `Runner` docstring does not describe the new public `on_progress`/`on_tick` contract: they run only on the thread iterating `run()`, never for dry runs or `plan()`, ordinary exceptions are suppressed, and capabilities receive a `progress` enqueue callable or None. The design expects a later TUI/API observer to rely on this. | File: src/tools/backup/runner.py:39 | Task: 3

[BOB] ⚪ When system tar exits 0 but fsync, chmod or replace then raises OSError, `on_finalize` has already emitted `finalizing` (tar_archive.py:523). The OSError then triggers the Python fallback (tar_archive.py:535, :263), which rewrites the whole archive while the live line shows `finalizing`, and a second `finalizing` follows. | File: src/tools/backup/capabilities/tar_archive.py:523 | Task: 2

[BOB] ⚪ Cannot statically verify: on a real 80-column TTY, the joined status for three or more active jobs updates in place, does not leave stale wrapped lines, and clears before each result line and the summary. | File: N/A | Task: 4

FIX:
- Post-join cancellation drain is unpinned — src/tools/backup/runner.py:128 — Add a test to `TestRunnerCancellation` in tests/tools/backup/progress_runner_cases.py. Monkeypatch `Runner._shutdown` to set a `joining` event before it calls the original. Make the capability wait for `cancel`, then for `joining`, then put a same-label `finalizing` event directly into `kwargs["progress"].args[0]` and return. Assert that the observer receives that event before the label's terminal result. The test must fail when line 128 is deleted.
- Factory name hides the boundary emission — src/tools/backup/capabilities/tar_archive.py:48 — Rename `_archive_callbacks` to a verb that names the side effect, such as `_start_archiving_progress`, and update the call at tar_archive.py:258. Behavior does not change.
- `on_result` failure cancels running archives and leaks a traceback — src/tools/backup/cli.py:106 — In `_LiveProgress.finish`, wrap `self.refresh()` in `contextlib.suppress(Exception)` so KeyboardInterrupt still reaches the retry loop. Change progress_cli_cases.py:387 to assert that the result line still prints and the run continues.
- Test-seam alias has no comment — src/tools/backup/runner.py:11 — Add a one-line comment saying the separate binding keeps the progress queue out of the `backup.runner.queue.Queue` completion-queue monkeypatch seam.
- Observer contract is undocumented — src/tools/backup/runner.py:39 — Extend the `Runner` docstring with the `on_progress`/`on_tick` semantics: calling thread only, wake-up at least every 0.2 s while idle, suppressed for dry runs and `plan()`, ordinary exceptions swallowed, and capabilities get a `progress` enqueue callable or None.

VERIFY:
- Real-TTY rendering of multiple joined jobs — Configure three instances with labels of at least 10 characters and large sources. Run `backup --jobs 3` on an 80-column terminal. Confirm the status redraws in place without leftover wrapped lines, and that it is cleared before each result line and before the summary.

KNOWN:
- Repeated `finalizing` after a system-tar fallback that fails after the stream closed — The fallback on post-close OSError is existing PRD 00111 behavior. The design defines `finalizing` as "stream closed", which held when the first event fired. Fixing the phase needs a design decision (move finalize after fsync, or re-emit `archiving` before the fallback). The terminal StepResult stays authoritative, and the path needs a rare fsync/chmod/replace failure.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Unavailable: source helper nesting guard, exit 3. No output was reused.

## Decision gate

No unresolved critical or high finding. R1-R4 are actionable consensus tail findings. Re-emit activity-only archiving before Python fallback without moving the stream-close finalization boundary or introducing a percentage. R5-R14 are single-voice medium/low findings and are discarded under source policy; the ledger retains every finding and reason. R10, R11 and R12 also describe explicit reviewed design choices (tick hook, final cumulative flush, bounded cancellation-aware backpressure). R14 names no exact runnable verification command, so it is not queued. No verification item was silently converted into a passing check.

Verdict: 14 findings
Tests: 6372 passed, 0 failed, 16 skipped (suite run this cycle)
