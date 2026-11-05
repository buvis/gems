# PRD 00117 cycle 2 Tail sweep work

Tasks 3 and 4 completed sequentially through the normal work pipeline. Phase and next_phase remain review; cycle 2, cap 2, original tasks 1/2 attempts, work_start_sha, reviewed implementation audit, and review receipts remain unchanged. No completion roster or phase transition was run here.

Task 3 adds whole-tree/source-equality real case-alias tests, selected-file case-alias coverage, and distinct hard-link output acceptance across both engines and run/dry_run/plan. `_same_path` distinguishes one directory entry reached through aliases from separate hard-link entries. Existing error conversion and final-symlink behavior are retained. The private selected parameter is required. The Unreleased changelog records the hard-link fix.

Task 4 used the source micro lane: two findings, one clean file, no CRITICAL finding, net -24 lines. It removes the redundant invalid-items test and duplicate error/selected-directory values, retaining all new task-3 tests.

## Gates and commits

- Task 3 initial Tess tests: 6 failed, 120 passed, exit 1 after test commit. All failures were the hard-link cases. The new case-alias cases ran on this case-insensitive filesystem without skips.
- Test author quality/shape and style gates passed. One Tess quality retry added the missing regular-file alias counterpart; 132 passed. Native Ivan preserved that counterpart before commit.
- Task 3 final narrow gate: `uv run pytest tests/tools/backup/test_bundle_case_containment.py -q --tb=line`: 132 passed, exit 0.
- Task 4 final narrow gate: same command: 84 passed, exit 0. The 48 removed cases are redundant legacy cases.
- 3: style_gate: clean, split_hygiene: clean.
- 4: style_gate: clean, split_hygiene: clean.
- Task 3 self_deslop skipped:trivial (implementation commit net +13 lines). Task 4 self_deslop skipped:trivial (micro lane). Devon skipped by the sonnet lean tier. No reflow tripwire hits.
- Real commit hooks rejected task 3 once for PLR0911 and formatting; one native Ivan repair fixed it, and the sole repaired commit retry passed. Task 4's hook removed one trailing blank line; its sole repaired commit retry passed. No hooks were bypassed.
- Commits: `aba599ec` initial tests; `b476b7fc` regular-file alias test; `95dc757e` implementation/changelog; `b7cbc2fd` duplicate test removal.
- `uv run ruff check src/tools/backup tests/tools/backup`: passed. `uv run mypy src/tools/backup`: 11 files clean.

## Final verification

The full suite ran once through `autopilot verify --cycle 2` with gate command `env -u GIT_AUTHOR_NAME -u GIT_AUTHOR_EMAIL -u GIT_COMMITTER_NAME -u GIT_COMMITTER_EMAIL BUVIS_CONFIG_DIR=/Users/bob/git/src/github.com/buvis/gems/docs/dev/tmp/verification-config python3 docs/dev/tmp/00117-review-gate.py`. That existing helper runs `uv run pytest` and emits structured counts. The isolated config contains `buvis-postup.yaml` with `roots: []`, preserving the earlier review's test isolation without editing operator config. Result: PASS 6654 FAIL 0 SKIP 16 EXIT 0, with 1 xfailed. `autopilot verify` returned 0, recorded true, dirty false, timed_out false, and wrote last-verification.json for `b7cbc2fdad77fcb3a4416978c7721ee9b2c6eb34`, cycle 2. No record was hand-written. The complete gate log is `00117-tail-sweep-full-suite.log` beside this report.

## Per-task reviews

Both Pat reviews used the real installed use-sonnet wrapper, tool-less `-t ""`, no edit/bypass flags, and `CLAUDE_CODE_EFFORT_LEVEL=high`. Raw API request metadata confirms `output_config.effort: high`; assistant metadata confirms served model `claude-sonnet-5-5`. Task 3 session `cda082ea-598c-4d26-88df-f0980fd28f22`, dispatch `6eb8ed54`: all three closures resolved, NO FINDINGS. Task 4 session `81fa854d-af47-4f6e-a120-ec69bb18ed21`, dispatch `515c6580`: both closures resolved, NO FINDINGS. Both outputs passed parse_review.py. Raw sessions and review text are preserved in `00117-tail-sweep-model-evidence/pat-{3,4}.{jsonl,txt}`.

## Implementation provenance

All contributors used observed OpenAI `gpt-6.1-sol`, medium. The canonical native raw logs and exact per-line/file hashes are in `00117-tail-sweep-model-evidence/native-contributors.json`. They cover Tess initial (`74ba12e3`), Ivan initial (`b3f8a271`, including its correction before final return), Tess quality retry (`df3baf11`), Ivan commit-hook repair (`7958465c`), coordinator changelog contribution for task 3, and micro-lane coordinator edit for task 4. The coordinator raw snapshot was captured after its final source/test edit and includes both contributions. No other model contributed implementation. Pat is read-only and excluded from implementation provenance.

Task 3 followed source routing row 7: no qwen eligibility metadata; no Codex eligibility metadata, so no interception. Native Claude worker becomes native Codex at logical sonnet under the host contract. A read-only Codex hook doctor also observed 4 ok, 7 stale, 5 broken; it did not change the routing verdict, launch an external implementor, or rewrite the historical probe. Both providers have independent completion-review routes under the host. No Gemini/UI route was selected. Task 4 followed the source micro lane and records implementor orchestrator. Existing state enum codex on task 3 identifies the native launcher separately from actual provider/model.

The b3f8a271 telemetry row was initially closed on an early completion message; its final result was then observed and a final end row records that correction. Every worker and reviewer process was awaited; no timeout, orphan worker, stale worktree, or task plan was left by this work phase. The unrelated existing braid worktree is retained. No cycle-2 verification-check queue exists.

## Assumptions

All Tess and Ivan reports: ASSUMPTIONS: none. The coordinator made no behavioral assumptions. The existing unrelated PRD 00112 ledger is preserved, with its current content:

```text
# PRD 00112 assumptions

Task 1: Tess and Ivan reported ASSUMPTIONS: none.

## 2: Emit archive engine progress
Tess quality retry: Clearing PATH represents unavailable system tar; real fallback-message assertion passed. Other test writers and implementors reported none.

## 6: Tail sweep archive progress

Tess: System tar is available. Empty-input coverage uses an empty file. Persistent filesystem failure preserves the observed OSError behavior.

Ivan initial: Fallback retains the system-tar engine string so done_bytes remains None. The assumption that duplicate archiving on early fallback was acceptable was rejected against the existing exact-event test and corrected by the bounded repair. Ivan repair reported none.

## 7: Tail sweep observer documentation

Ivan: Plan suppression means the planning phase emits no progress events. The idle tick interval comes from completed.get(timeout=0.2). Coordinator verified both against Runner.plan/_plan and _collect_completion; paused-yield timing is stated explicitly.
```
