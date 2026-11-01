---
prd: docs/dev/project-management/prds/wip/00111-backup-parallel-jobs-and-cancellation-v1.md
review: 1
date: 2026-11-01
head_sha: 36692a6139c6b94f4dc999187f9b8945f7b02a5e
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
dispatch_rows:
  bob: 77eaf55a
---

# Review: 00111-backup-parallel-jobs-and-cancellation-v1

Diff range: `9a7f78c8eb0e4148181584f92eb649cfec590034..36692a6139c6b94f4dc999187f9b8945f7b02a5e`

codex_rung_guard: not fired
provider_review_guard: satisfied
autocodex_alice_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00111-c1-fresh-20261101-alice.txt.receipt.json
autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00111-c1-fresh-20261101-blake.txt.receipt.json
autocodex_bob_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00111-c1-fresh-20261101-bob.txt.receipt.json

The actual-model provider guard supersedes the legacy Codex rung guard. Eve did not run.
All three fresh isolated lanes used Kiro, Anthropic claude-opus-5.5, xhigh.
The implementation audit covers all five completed tasks, test authors, retries and repairs.
Review-route validated its fingerprint and evidence hashes before dispatch.
Recovery input hashes passed. The product tree is unchanged from the supplied gate revision.
Blake received only the specification and test gate, with native read/search tools.
Carl: skipped (no UI change; optional specialist). No Gemini implementation contribution.

## Review Summary

Reviewed: five completed tasks. Full review; cycle 1, cap 2.
All required reviewers completed successfully. Every raw rubric verdict follows below.
No Critical or High finding remains. Medium/Low findings receive the source decision gate and tail sweep.

Consolidation used consolidate_findings.py, with coordinator corrections:
the two-active/two-queued scenario raised by Blake and Bob is one finding R18;
the script merged Bob's distinct repeated-interrupt test gap into R1 because both cite runner.py.
That gap is restored as R24. R20 is absorbed into R18. All raw outputs remain intact.
R3 includes exceptional child cleanup and the real-time kill-grace tests; Bob's separate
system-engine pre-publication coverage observation remains R9, with its original minority status.
No mechanical test-check finding or prior failed-check queue exists in this cycle's context.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟡 | Low Two narrow Ctrl-C timing windows in `_execute`. First, a KeyboardInterrupt that lands after `Queue.get` has dequeued a future but before `pending.pop(future)` (runner.py:119-120) leaves that future in `pending` with nothing in the queue. The next `completed.get()` then blocks forever, and the inner handler swallows every later Ctrl-C. Second, a KeyboardInterrupt inside `executor.submit`, for example while `Thread.start` waits, drops an instance already popped from `remaining`, so it gets no terminal result. Fix: after `_shutdown`, every future is done, so collect from `pending` directly instead of waiting on the queue | src/tools/backup/runner.py:119 | 2 | ALICE, BLAKE, BOB |
| R2 | [3/3] | 🟡 | Low CHANGELOG has three overlapping Added bullets for one feature. Bullets 1 and 2 both describe the default of three concurrent instances and the preservation of completed results. The design asked for one entry that mentions `--jobs` and cancellation. Merge them into one bullet | CHANGELOG.md:12 | 4 | ALICE, BLAKE, BOB |
| R3 | [2/3] | 🟡 | Medium Some new system-tar lifecycle paths have no test. No test raises an exception other than cancellation after tar has spawned and then checks that the live child is terminated and reaped and that the `tar invocation failed` fallback is returned (a grep for that string in tests finds nothing). No test covers the suppressed `ProcessLookupError` race when the child has already exited. Kill escalation is covered only by the stubborn stub, which waits a real 5 seconds in each of its two parameter cases. The design asked for a controlled Popen fake that covers terminate, the 5-second grace, kill, already-exited races and exceptional cleanup without real waits | tests/tools/backup/test_parallel_runner.py:223 | 1 | ALICE, BOB |
| R4 | [2/3] | 🟡 | Medium Two cancel checks run back to back. `_run_system_tar` calls `_check_cancel(cancel)` right after `communicate` succeeds (tar_archive.py:514), and its only caller calls it again as soon as the function returns. Delete the check at tar_archive.py:462. No work runs between the two checks, so behavior does not change | src/tools/backup/capabilities/tar_archive.py:462 | 1 | ALICE, BOB |
| R5 | [2/3] | 🟡 | Medium `Runner.run` has a `finished` flag (runner.py:63) and calls `cancel.set()` in its `finally` (runner.py:80). That duplicates the `finally` in `_execute`, which already sets the event and joins the executor when the generator is abandoned or fails. Before `_execute` starts, no worker exists, so setting the event there has no effect. Remove the flag and that branch, and keep only the `cancelled_names` and `_cancel = None` lines in the `finally` | src/tools/backup/runner.py:80 | 2 | ALICE, BOB |
| R6 | [2/3] | 🟡 | Medium `cast("Generator[StepResult, None, None]", runner.run(plan))` hides a real requirement: `_run_plan` calls `.close()`, which fails with AttributeError on any plain Iterator, the type `Runner.run` declares. That is why the mocks in test_backup_cli.py had to change from `iter([...])` to `_steps()` generators. Annotate `Runner.run` as `-> Generator[StepResult, None, None]` and drop the cast. A Generator is still an Iterator, so the design contract still holds | src/tools/backup/cli.py:237 | 3 | ALICE, BOB |
| R7 | [2/3] | ⚪ | Low Unrequested documentation cuts. The `_write_archive_system_tar` docstring lost the reasons for `--no-recursion` (a listed directory must not be re-expanded, which would re-add excluded content) and for NUL delimiting (no newline injection). The `_report_steps` and `_run_plan` docstrings lost the return-value contract (a nonzero exit so cron sees a failed backup). Restore the removed rationale | src/tools/backup/capabilities/tar_archive.py:440 | general | ALICE, BOB |
| R8 | [2/3] | ⚪ | `_cleanup_tar_process` sends terminate and kill only to the tar pid, although `start_new_session=True` gives tar its own process group (tar_archive.py:502, tar_archive.py:527-533). On Linux, GNU tar `-z` forks gzip, which inherits the stderr pipe. So the post-kill `process.communicate()` with no timeout (tar_archive.py:533) waits for gzip to exit, not the bounded wait promised in the PRD Risks section. `os.killpg` would close this gap | src/tools/backup/capabilities/tar_archive.py:533 | Phase 0 | BLAKE, BOB |
| R9 | [1/3] | 🟡 | Two new system-tar behaviours have no test. First, removing the cancel check between fsync/chmod and `os.replace` (tar_archive.py:475) breaks no test: no test sets the event after `communicate` returns, and the Python engine has `test_cancel_cleans_when_requested_during_fsync` but the system engine has no counterpart. Second, the design's "any other exception after spawn must stop/reap the live child before returning the invocation-failure fallback" is untested: no test makes `communicate` raise `OSError` while `poll()` is None | tests/tools/backup/test_parallel_runner.py:327 | 1 | BOB |
| R10 | [1/3] | ⚪ | Low The `Runner` class docstring still lists only label, excludes and dry_run as runtime kwargs. It does not mention `jobs`, `now`, `cancel`, completion-order yielding, `interrupted` or `cancelled_names` | src/tools/backup/runner.py:27 | 2 | ALICE |
| R11 | [1/3] | ⚪ | Low This test runs with `jobs=1`, which makes the order deterministic, but its label check was weakened to set equality. The `zip(results, engines, strict=True)` that follows still depends on result order, so the weaker check hides that dependency. Restore `== list(outputs)` | tests/tools/backup/test_plan_runner.py:411 | 2 | ALICE |
| R12 | [1/3] | ⚪ | Low The review range contains changes outside PRD 00111: Node 22.23→26.13 in `.mise.toml` and `publish.yml`, and svelte and milkdown bumps in the bim and postup frontends. Confirm they come from separate dependency commits. If not, split them out of this PRD | .github/workflows/publish.yml:46 | general | ALICE |
| R13 | [1/3] | ⚪ | Low The recorded gate covers only pytest. The PRD exit criteria also require clean ruff and mypy runs. The coordinator should run `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` | N/A | general | ALICE |
| R14 | [1/3] | ⚪ | The PRD says `cancel` goes to every capability call, but `Runner._plan` calls `capability.plan(**call_kwargs)` without it (runner.py:157-164). This is harmless while plan only reads metadata, but it does not match the PRD wording, and a future capability whose plan does I/O could not be cancelled | src/tools/backup/runner.py:164 | Phase 1 | BLAKE |
| R15 | [1/3] | ⚪ | The Capability protocol docstring still says the runner lets FatalError through and turns only other exceptions into failed steps (capabilities/__init__.py:21-24). `_run_instance` now turns a worker FatalError into a failed step (runner.py:208, asserted by test_failure_isolated_from_other_workers). The code follows the PRD; the docstring is out of date | src/tools/backup/capabilities/__init__.py:21 | Phase 1 | BLAKE |
| R16 | [1/3] | ⚪ | Ctrl-C has no way out when a writer is slow to see `cancel`. `_walk_tree` and `_select_items` check `cancel` only after the whole walk (tar_archive.py:183-184), and the Python engine checks only between members. Every repeated Ctrl-C is swallowed (runner.py:122, runner.py:136, cli.py:50, cli.py:248), so a large or stalled source tree keeps the process alive until SIGTERM or SIGKILL. The docs mention only the per-member delay (docs/source/tools/backup.rst:43-44) | src/tools/backup/capabilities/tar_archive.py:183 | Phase 0 | BLAKE |
| R17 | [1/3] | ⚪ | `_report_steps` re-renders the pending step after any KeyboardInterrupt. That includes one that lands after `_report_step` printed and the counter went up but before `pending = None` (cli.py:40-47). A Ctrl-C at that moment prints the step twice and counts it twice in the summary | src/tools/backup/cli.py:40 | Phase 2 | BLAKE |
| R18 | [2/3] | ⚪ | The Test Strategy case "interrupt with two active and two queued" is not tested as written. The interrupt tests use three instances with `jobs=2`: one completed, one active, one queued (tests/tools/backup/test_parallel_runner.py:554, tests/tools/backup/test_parallel_cli.py:141). The exit-130 CLI test is in test_parallel_cli.py, so the PRD's success-metric command `pytest tests/tools/backup/test_parallel_runner.py` never runs the exit-130 path | tests/tools/backup/test_parallel_cli.py:141 | Phase 2 | BLAKE, BOB |
| R19 | [1/3] | ⚪ | Runner has public members beyond the PRD's exports (`Runner(cfg, dry_run, jobs)`, `Runner.interrupted`): `request_cancel()` and `cancelled_names` (runner.py:45, runner.py:47). The CLI needs them to handle Ctrl-C during rendering and to name unfinished instances, so they add no new feature, but they are undocumented API | src/tools/backup/runner.py:47 | Phase 1 | BLAKE |
| R21 | [1/3] | ⚪ | `_run_instance` materializes the capability iterator, so a later `ArchiveCancelled` or exception throws away earlier successful results from a multi-result capability | src/tools/backup/runner.py:205 | 2 | BOB |
| R22 | [1/3] | ⚪ | `start_new_session=True` takes tar out of the terminal's process group. SIGHUP (terminal close) or SIGTERM to Python orphans a running tar, which keeps writing and leaves a `.tmp` sibling | src/tools/backup/capabilities/tar_archive.py:502 | 1 | BOB |
| R23 | [1/3] | ⚪ | `KeyboardInterrupt` is an asynchronous exception, so a few bytecode positions stay outside the handlers: generator entry before `run`'s try, and the `_execute` loop back-edge after the inner try. An interrupt there escapes the generator. Unyielded results are then dropped and unsubmitted names are left out of `cancelled_names` ("interrupted: no unfinished instances") | src/tools/backup/runner.py:97 | 2 | BOB |
| R24 | [1/3] | ⚪ | No test interrupts `_shutdown`'s join a second time to show the cleanup still completes after repeated Ctrl-C | src/tools/backup/runner.py:131 | 2 | BOB |

## Alice

```text
[ALICE] 🟡 Medium Some new system-tar lifecycle paths have no test. No test raises an exception other than cancellation after tar has spawned and then checks that the live child is terminated and reaped and that the `tar invocation failed` fallback is returned (a grep for that string in tests finds nothing). No test covers the suppressed `ProcessLookupError` race when the child has already exited. Kill escalation is covered only by the stubborn stub, which waits a real 5 seconds in each of its two parameter cases. The design asked for a controlled Popen fake that covers terminate, the 5-second grace, kill, already-exited races and exceptional cleanup without real waits | File: tests/tools/backup/test_parallel_runner.py:223 | Task: 1
```
```text
[ALICE] 🟡 Medium Two cancel checks run back to back. `_run_system_tar` calls `_check_cancel(cancel)` right after `communicate` succeeds (tar_archive.py:514), and its only caller calls it again as soon as the function returns. Delete the check at tar_archive.py:462. No work runs between the two checks, so behavior does not change | File: src/tools/backup/capabilities/tar_archive.py:462 | Task: 1
```
```text
[ALICE] 🟡 Medium `Runner.run` has a `finished` flag (runner.py:63) and calls `cancel.set()` in its `finally` (runner.py:80). That duplicates the `finally` in `_execute`, which already sets the event and joins the executor when the generator is abandoned or fails. Before `_execute` starts, no worker exists, so setting the event there has no effect. Remove the flag and that branch, and keep only the `cancelled_names` and `_cancel = None` lines in the `finally` | File: src/tools/backup/runner.py:80 | Task: 2
```
```text
[ALICE] 🟡 Medium `cast("Generator[StepResult, None, None]", runner.run(plan))` hides a real requirement: `_run_plan` calls `.close()`, which fails with AttributeError on any plain Iterator, the type `Runner.run` declares. That is why the mocks in test_backup_cli.py had to change from `iter([...])` to `_steps()` generators. Annotate `Runner.run` as `-> Generator[StepResult, None, None]` and drop the cast. A Generator is still an Iterator, so the design contract still holds | File: src/tools/backup/cli.py:237 | Task: 3
```
```text
[ALICE] ⚪ Low Two narrow Ctrl-C timing windows in `_execute`. First, a KeyboardInterrupt that lands after `Queue.get` has dequeued a future but before `pending.pop(future)` (runner.py:119-120) leaves that future in `pending` with nothing in the queue. The next `completed.get()` then blocks forever, and the inner handler swallows every later Ctrl-C. Second, a KeyboardInterrupt inside `executor.submit`, for example while `Thread.start` waits, drops an instance already popped from `remaining`, so it gets no terminal result. Fix: after `_shutdown`, every future is done, so collect from `pending` directly instead of waiting on the queue | File: src/tools/backup/runner.py:119 | Task: 2
```
```text
[ALICE] ⚪ Low CHANGELOG has three overlapping Added bullets for one feature. Bullets 1 and 2 both describe the default of three concurrent instances and the preservation of completed results. The design asked for one entry that mentions `--jobs` and cancellation. Merge them into one bullet | File: CHANGELOG.md:12 | Task: 4
```
```text
[ALICE] ⚪ Low Unrequested documentation cuts. The `_write_archive_system_tar` docstring lost the reasons for `--no-recursion` (a listed directory must not be re-expanded, which would re-add excluded content) and for NUL delimiting (no newline injection). The `_report_steps` and `_run_plan` docstrings lost the return-value contract (a nonzero exit so cron sees a failed backup). Restore the removed rationale | File: src/tools/backup/capabilities/tar_archive.py:440 | Task: general
```
```text
[ALICE] ⚪ Low The `Runner` class docstring still lists only label, excludes and dry_run as runtime kwargs. It does not mention `jobs`, `now`, `cancel`, completion-order yielding, `interrupted` or `cancelled_names` | File: src/tools/backup/runner.py:27 | Task: 2
```
```text
[ALICE] ⚪ Low This test runs with `jobs=1`, which makes the order deterministic, but its label check was weakened to set equality. The `zip(results, engines, strict=True)` that follows still depends on result order, so the weaker check hides that dependency. Restore `== list(outputs)` | File: tests/tools/backup/test_plan_runner.py:411 | Task: 2
```
```text
[ALICE] ⚪ Low The review range contains changes outside PRD 00111: Node 22.23→26.13 in `.mise.toml` and `publish.yml`, and svelte and milkdown bumps in the bim and postup frontends. Confirm they come from separate dependency commits. If not, split them out of this PRD | File: .github/workflows/publish.yml:46 | Task: general
```
```text
[ALICE] ⚪ Low The recorded gate covers only pytest. The PRD exit criteria also require clean ruff and mypy runs. The coordinator should run `uv run ruff check src/tools/backup tests/tools/backup` and `uv run mypy src/tools/backup` | File: N/A | Task: general
```

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

## Blake

```text
[BLAKE] 🟡 Ctrl-C handling can lose a result or hang the run. If a KeyboardInterrupt lands between `pending[future] = name` and `future.add_done_callback(completed.put)` (runner.py:115-116), or after `completed.get()` takes a future but before `pending.pop` (runner.py:119-120), a future stays in `pending` but never reaches `completed`. The untimed `completed.get()` then blocks forever. Every later Ctrl-C is caught at runner.py:122 and goes back into the same get, so Ctrl-C can no longer stop the run. An interrupt just after `remaining.popleft()` (runner.py:113) or `pending.pop` (runner.py:120) instead drops that instance's StepResult, and the instance is not named in the "interrupted:" message. Suggested fix: wait on the futures themselves (`concurrent.futures.wait(pending, return_when=FIRST_COMPLETED)`, or a timed get that rescans `done()`), and remove a future from `pending` only after its results are in `ready` | File: src/tools/backup/runner.py:119 | Task: Phase 1
```
```text
[BLAKE] ⚪ The PRD says `cancel` goes to every capability call, but `Runner._plan` calls `capability.plan(**call_kwargs)` without it (runner.py:157-164). This is harmless while plan only reads metadata, but it does not match the PRD wording, and a future capability whose plan does I/O could not be cancelled | File: src/tools/backup/runner.py:164 | Task: Phase 1
```
```text
[BLAKE] ⚪ The Capability protocol docstring still says the runner lets FatalError through and turns only other exceptions into failed steps (capabilities/__init__.py:21-24). `_run_instance` now turns a worker FatalError into a failed step (runner.py:208, asserted by test_failure_isolated_from_other_workers). The code follows the PRD; the docstring is out of date | File: src/tools/backup/capabilities/__init__.py:21 | Task: Phase 1
```
```text
[BLAKE] ⚪ Ctrl-C has no way out when a writer is slow to see `cancel`. `_walk_tree` and `_select_items` check `cancel` only after the whole walk (tar_archive.py:183-184), and the Python engine checks only between members. Every repeated Ctrl-C is swallowed (runner.py:122, runner.py:136, cli.py:50, cli.py:248), so a large or stalled source tree keeps the process alive until SIGTERM or SIGKILL. The docs mention only the per-member delay (docs/source/tools/backup.rst:43-44) | File: src/tools/backup/capabilities/tar_archive.py:183 | Task: Phase 0
```
```text
[BLAKE] ⚪ `_cleanup_tar_process` sends terminate and kill only to the tar pid, although `start_new_session=True` gives tar its own process group (tar_archive.py:502, tar_archive.py:527-533). On Linux, GNU tar `-z` forks gzip, which inherits the stderr pipe. So the post-kill `process.communicate()` with no timeout (tar_archive.py:533) waits for gzip to exit, not the bounded wait promised in the PRD Risks section. `os.killpg` would close this gap | File: src/tools/backup/capabilities/tar_archive.py:533 | Task: Phase 0
```
```text
[BLAKE] ⚪ `_report_steps` re-renders the pending step after any KeyboardInterrupt. That includes one that lands after `_report_step` printed and the counter went up but before `pending = None` (cli.py:40-47). A Ctrl-C at that moment prints the step twice and counts it twice in the summary | File: src/tools/backup/cli.py:40 | Task: Phase 2
```
```text
[BLAKE] ⚪ The Test Strategy case "interrupt with two active and two queued" is not tested as written. The interrupt tests use three instances with `jobs=2`: one completed, one active, one queued (tests/tools/backup/test_parallel_runner.py:554, tests/tools/backup/test_parallel_cli.py:141). The exit-130 CLI test is in test_parallel_cli.py, so the PRD's success-metric command `pytest tests/tools/backup/test_parallel_runner.py` never runs the exit-130 path | File: tests/tools/backup/test_parallel_cli.py:141 | Task: Phase 2
```
```text
[BLAKE] ⚪ The PRD asks for one `Added` line under `[Unreleased]`, but CHANGELOG.md has three overlapping lines. Lines 12 and 13 both announce default-three concurrency and joining workers on cancel | File: CHANGELOG.md:12 | Task: Phase 2
```
```text
[BLAKE] ⚪ Runner has public members beyond the PRD's exports (`Runner(cfg, dry_run, jobs)`, `Runner.interrupted`): `request_cancel()` and `cancelled_names` (runner.py:45, runner.py:47). The CLI needs them to handle Ctrl-C during rendering and to name unfinished instances, so they add no new feature, but they are undocumented API | File: src/tools/backup/runner.py:47 | Task: Phase 1
```

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
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

Checks the coordinator still needs to run (I could not run them under the read-only transport):
1. Run `uv run ruff check src/tools/backup tests/tools/backup`. This is part of the Phase 2 exit criteria.
2. Run `uv run mypy src/tools/backup`. This is part of the Phase 2 exit criteria.

I checked the `rg -c "\-\-jobs"` acceptance with grep instead of rg: `docs/source/tools/backup.rst` has several matches and `CHANGELOG.md` matches at line 12.

## Bob

```text
[BOB] 🟡 The runner's interrupt path can lose a completed future. A `KeyboardInterrupt` that lands after `completed.get()` has dequeued the future (inside `Queue.get`'s `notify`/`__exit__`), or in a main-thread `completed.put` (from `add_done_callback` on an already-done future, or from `shutdown(cancel_futures=True)` calling `Future.cancel`), leaves the future in `pending` but not in the queue. The later `completed.get()` then blocks forever. If the interrupt lands after `pending.pop(future)` but before `ready.extend(...)`, that instance gets no terminal result. The window is very narrow, but the result is a hang in exactly the path this PRD is meant to make clean | File: src/tools/backup/runner.py:119 | Task: 2
```
```text
[BOB] 🟡 Two new system-tar behaviours have no test. First, removing the cancel check between fsync/chmod and `os.replace` (tar_archive.py:475) breaks no test: no test sets the event after `communicate` returns, and the Python engine has `test_cancel_cleans_when_requested_during_fsync` but the system engine has no counterpart. Second, the design's "any other exception after spawn must stop/reap the live child before returning the invocation-failure fallback" is untested: no test makes `communicate` raise `OSError` while `poll()` is None | File: tests/tools/backup/test_parallel_runner.py:327 | Task: 1
```
```text
[BOB] 🟡 CHANGELOG has three overlapping Added entries for one feature. Lines 12 and 13 both say the default is three workers and completed results are preserved. The PRD asks for "an `Added` line" and the design for "one Added entry" | File: CHANGELOG.md:12 | Task: 4
```
```text
[BOB] 🟡 `cast("Generator[StepResult, None, None]", runner.run(plan))` claims a type the declared `Iterator` return does not promise, so `.close()` is only safe by convention. That forced every `return_value=iter([...])` patch in test_backup_cli.py and test_backup_phase2.py to become a generator. Simpler: annotate `Runner.run` as `Generator[StepResult, None, None]` (runner.py:53) and drop the cast and the `cast` import | File: src/tools/backup/cli.py:237 | Task: 3
```
```text
[BOB] 🟡 `Runner.run` keeps its own `finished` flag and calls `cancel.set()` on abnormal exit, which duplicates `_execute`'s `finally` (runner.py:126). The only exception that can escape before `_execute` starts is a preflight `FatalError`, and no workers exist at that point. Remove the flag and the `cancel.set()` and keep only the `cancelled_names`/`_cancel` reset | File: src/tools/backup/runner.py:63 | Task: 2
```
```text
[BOB] 🟡 tar_archive.py has redundant guards. `TarArchive.run` checks cancel at entry (:124) and `_run_validated` checks again (:163) with only cheap input validation between them. `_run_system_tar` checks after a successful `communicate` (:514) and the caller checks again immediately (:462). The `contextlib.suppress(ProcessLookupError)` wrappers (:526, :531) duplicate what CPython ≥3.9 `Popen.send_signal` already does (poll first, then suppress `ProcessLookupError`) | File: src/tools/backup/capabilities/tar_archive.py:124 | Task: 1
```
```text
[BOB] ⚪ The diff compresses existing comments and docstrings nobody asked to change. The system-tar docstring loses its `--no-recursion` reason (a listed directory would re-add excluded content) and the reason for NUL delimiting (a newline in a filename would inject an outside or absolute `-T` path). The `_report_steps`/`_run_plan` docstrings lose the cron-exit reasoning | File: src/tools/backup/capabilities/tar_archive.py:440 | Task: 1
```
```text
[BOB] ⚪ The `stubborn` × `previous` parametrization waits through the real 5-second terminate grace twice, about 10 s of suite time. The design called for a controlled `Popen` fake for kill escalation without real five-second waits | File: tests/tools/backup/test_parallel_runner.py:222 | Task: 1
```
```text
[BOB] ⚪ The PRD test scenario "interrupt with two active and two queued" is only tested with one active and one unsubmitted instance (3 instances, jobs=2) | File: tests/tools/backup/test_parallel_runner.py:554 | Task: 2
```
```text
[BOB] ⚪ `_run_instance` materializes the capability iterator, so a later `ArchiveCancelled` or exception throws away earlier successful results from a multi-result capability | File: src/tools/backup/runner.py:205 | Task: 2
```
```text
[BOB] ⚪ Only the direct tar child is signalled, and the final `process.communicate()` after `kill` has no timeout. A descendant that holds the pipes could block cleanup | File: src/tools/backup/capabilities/tar_archive.py:533 | Task: 1
```
```text
[BOB] ⚪ `start_new_session=True` takes tar out of the terminal's process group. SIGHUP (terminal close) or SIGTERM to Python orphans a running tar, which keeps writing and leaves a `.tmp` sibling | File: src/tools/backup/capabilities/tar_archive.py:502 | Task: 1
```
```text
[BOB] ⚪ `KeyboardInterrupt` is an asynchronous exception, so a few bytecode positions stay outside the handlers: generator entry before `run`'s try, and the `_execute` loop back-edge after the inner try. An interrupt there escapes the generator. Unyielded results are then dropped and unsubmitted names are left out of `cancelled_names` ("interrupted: no unfinished instances") | File: src/tools/backup/runner.py:97 | Task: 2
```
```text
[BOB] ⚪ No test interrupts `_shutdown`'s join a second time to show the cleanup still completes after repeated Ctrl-C | File: src/tools/backup/runner.py:131 | Task: 2
```

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

FIX:
- Interrupt can lose a dequeued future, hanging `completed.get()` or dropping a terminal result — src/tools/backup/runner.py:119 — in the cancel branch after `_shutdown` (runner.py:99-104), every future is already done. Collect results directly from `pending` (in insertion order), then `pending.clear()`, so the cancel path never blocks on the queue.
- System-tar pre-publication check and post-spawn non-cancel reaping are untested — tests/tools/backup/test_parallel_runner.py:327 — add a test that sets the event inside the system-tar `os.fsync`/`os.chmod` and asserts `ArchiveCancelled`, prior bytes unchanged and no `.tmp`. Add a Popen-fake test where `communicate` raises `OSError` with `poll()` None, asserting `terminate` plus `communicate(timeout=5.0)` and a returned `"tar invocation failed: ..."`.
- Three overlapping CHANGELOG Added entries — CHANGELOG.md:12 — merge lines 12-14 into one entry that covers `--jobs` (default 3), cooperative cancellation for both engines, and exit 130.
- Cast to `Generator` hides the `.close()` contract — src/tools/backup/cli.py:237 — annotate `Runner.run` (runner.py:53) as `Generator[StepResult, None, None]`, then use `steps = runner.run(plan)` and drop the `cast` import.
- Duplicate `finished`/`cancel.set()` in `Runner.run` — src/tools/backup/runner.py:63 — delete `finished` (:63, :78) and `if not finished: cancel.set()` (:80-81).
- Redundant guards in tar_archive — src/tools/backup/capabilities/tar_archive.py:124 — keep the entry check in `run` and drop the one at :163. Drop the post-communicate check at :514, because :462 covers it. Drop the `contextlib.suppress(ProcessLookupError)` wrappers at :526 and :531.
- Removed rationale comments and docstrings — src/tools/backup/capabilities/tar_archive.py:440 — restore the `--no-recursion` and NUL-injection reasoning in the system-tar docstring, and the cron-exit reasoning in the `_report_steps` (cli.py:32) and `_run_plan` (cli.py:222) docstrings.
- Real 5-second grace waits in the stubborn-tar test — tests/tools/backup/test_parallel_runner.py:222 — run the stubborn real process for `previous=None` only, or replace it with a Popen fake whose `communicate(timeout=5.0)` raises `TimeoutExpired`, and assert `kill` and a final `communicate()`.
- The two-active/two-queued interrupt scenario is not tested — tests/tools/backup/test_parallel_runner.py:554 — add a 4-instance, jobs=2 case: both active workers see the event and the two unsubmitted instances never start.

VERIFY:
- (none)

KNOWN:
- Successful prefix lost from a multi-result capability on a later cancel or failure — recorded as a non-blocker in both design-review dispatches; no current capability publishes more than one result.
- Direct-child-only signalling and the untimed final `communicate()` — design names arbitrary descendant supervision as outside v1; the stub test deliberately uses a direct child.
- Orphaned tar on SIGHUP/SIGTERM because of `start_new_session=True` — deliberate design choice so Ctrl-C reaches only the runner; the design forbids library signal handlers in v1.
- Async `KeyboardInterrupt` windows outside the handlers (generator entry, loop back-edge) — exception-based interrupts cannot be made safe at every bytecode without a SIGINT handler, which the design excludes. The hang variant is fixed under FIX.
- No test for repeated Ctrl-C during `_shutdown` — dispatch 2 of the design review recorded this as a future test improvement, not a v1 requirement.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Coordinator checks and decisions

Ruff: `uv run ruff check src/tools/backup tests/tools/backup` exited 0, All checks passed.
Mypy: `uv run mypy src/tools/backup` exited 0, no issues in 11 source files.
The reported unused override-section note is informational.
These checks close the runtime requests from Alice and Blake; Bob's VERIFY bucket is empty.

The full-suite evidence is 00111-verification-final.log and the recovery context.
It records Python 3.13, 6218 passed, 16 skipped, one expected xfail, and exit 0.
The copied canonical Tests line below preserves the stage's counts and suffix.
Python 3.14 baseline failures remain owned by held PRDs 00113/00114.

R1-R7 and R18 are bounded actionable findings selected for the tail sweep.
R8 is a settled v1 limitation: the reviewed design explicitly scopes lifecycle ownership
to the direct tar child and records descendant-held-pipe cleanup as a non-blocker.
It is deferred durably rather than silently expanded into process-group supervision.
Every remaining minority Medium/Low row is discarded by the mandatory single-voice rule,
with the exact source issue and disposition retained in the ledger and state decisions.
R12's dependency changes are separate commits f6aee2f2 and 0cd175b6, outside this implementation.

Verdict: 23 findings
Tests: 6218 passed, 0 failed, 16 skipped (suite run this cycle)

