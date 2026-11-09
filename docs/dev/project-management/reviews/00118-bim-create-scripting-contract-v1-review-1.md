---
prd: docs/dev/project-management/prds/done/00118-bim-create-scripting-contract-v1.md
review: 1
date: 2026-11-09
head_sha: 2f6aee1523307ab9504e118abc81f3c27760c67f
codex_thread_id: 01a1c06b-c782-7051-8491-2a82e740178a
reviewers: alice,blake,bob,carl,eve
agents:
  alice: available
  blake: available
  bob: available
  carl: available
  eve: available
dispatch_rows:
  bob: 2759e323
  carl: 6b831412
---

# Review: 00118-bim-create-scripting-contract-v1

Diff range: `a087e05e3543d2b0c199fba8e0ccd5dabf5bf8ad..2f6aee1523307ab9504e118abc81f3c27760c67f`

codex_rung_guard: fired (3 codex-implemented task(s))

Standalone run (no `state.json`; the 202611090739 batch had closed). The guard count comes from the archived state snapshot `autopilot/reports/00118-replan-1-state-before.json`: tasks 1, 2 and 3 of this PRD carry codex implementor attempts, so the doubt lens did not run on codex alone and Eve joined as the fifth lens. The three bim-create PRDs were moved to `prds/done/` before this review ran, so the review target was taken from `prds/done/`, not `prds/wip/`. Tasks 1-3 were built by the batch, tasks 4-5 and the sibling PRDs attended on this branch, so the reviewed diff is the whole branch scoped to code, tests and docs (`review-paths` marker: `AGENTS.md CHANGELOG.md README.md pyproject.toml docs/source src tests`; the autopilot store was excluded). Reviewers judged it against PRD 00118; the implementation-aware prompts also carried the 00118 design doc. Tasks: none in a task store (standalone), the task table is empty. Pack: failed (engram not registered for this worktree). Fail-first replay: the path-scoped gather left no diff base in the scope line, so the replay ran by hand against `a087e05e` and its block was spliced into the staged context before the prompts were rendered. Carl ran on copilot, model gemini-3.8-flash. Eve's saved output differs from her report in one token: the repo's aegis hook refuses to write a file containing a literal lint-suppression marker, so the quoted marker in her second KNOWN item is spelled "noqa comment" in `docs/dev/tmp/eve-output-20261109-00118.txt`. Consolidation: the canonical script ran over five outputs; Eve's FIX, VERIFY and KNOWN buckets are not issue lines, so the coordinator folded her FIX items and her VERIFY item into the table by hand and merged five groups of rows describing one defect (Consolidation notes). Her VERIFY item is not queued (standalone run, no work phase).

## Review Summary

Reviewed: 0 tasks in a task store (standalone run; the work is batch commits `263a5719`..`3add96b5` for tasks 1-3, `9b45d45a` for tasks 4-5, and the shared fix commits `98cf6d25` and `2f6aee15`)
PRDs checked: 00118-bim-create-scripting-contract-v1 (00119 and 00120 reviewed in their own cycles)

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex)
- Carl: ✅ Available (copilot, gemini-3.8-flash)
- Eve: ✅ Available (fable)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/5] | 🟡 | `create_note` (78 lines) and `_create_note_scripted` (84 lines) exceed the 50-line limit (mechanical facts). Split input reading, params and command construction, and result rendering into helpers. | src/tools/bim/note_write_cli.py:114 | 4 | ALICE, BOB, CARL |
| R2 | [4/5] | 🟡 | `tests/tools/bim/test_create_note.py` is 952 lines, over the 800-line limit, and `TestArticleWorkflow` holds two non-article tests (lines 910 and 935). Move `TestVaultLinks` and `TestArticleWorkflow` into their own module and the two misfiled tests into `TestCommandCreateNote`. | tests/tools/bim/test_create_note.py:1 | 3 | ALICE, BOB, CARL, EVE |
| R3 | [4/5] | 🟡 | `test_cancel_exits` has no assertion; it only proves cancel does not raise. Pre-existing test, not touched by this diff; Eve's fix is `mocker.spy(app, "exit")` and `assert_called_once()`. | tests/tools/bim/tui/test_create_note.py:73 | general | BOB, CARL, ALICE, EVE, mech-check |
| R4 | [3/5] | 🟡 | The exit-1 contract is incomplete: SKILL.md:174 and bim.rst claim every note command exits 1 when it fails, but usage failures still exit 0 (`resolve_paths` with no paths or with paths plus a query, `import` of several paths interactively, `edit` with no single existing path; verified live: `bim show` with no paths prints the failure and exits 0). The failed-`CommandResult` path of `edit_note` has no exit-code test either. Add `ctx.exit(1)` after those `console.failure` calls, flip the three handler tests Eve names, and add the `edit` case. | src/tools/bim/note_write_cli.py:312 | 4 | EVE, ALICE, BLAKE |
| R5 | [3/5] | 🟡 | Reservation close handling: if `os.fstat` on the descriptor raises, `reservation` stays `None` and the zero-byte placeholder this invocation created stays on disk, blocking the id (unpinned by `test_inspection_failure_closes_reservation_and_skips_save_and_hooks`); the `except BaseException: fstat; close; raise` retry around `os.close` discards the `fstat` result and exists only to satisfy a test that patches `os.close` to raise. Reduce to `try: reservation = os.fstat(descriptor) finally: os.close(descriptor)` and pin the placeholder behaviour. | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:84 | 2 | ALICE, CARL, EVE |
| R6 | [2/5] | 🟠 | Every note `bim create` writes now has mode 0600 instead of 0644: `execute` reserves the path with `os.open(..., 0o600)` and `atomic_write` keeps an existing target's mode, so the placeholder's bits stick (confirmed live in a scratch vault by both reviewers; base code produced 0644). A behaviour change the spec did not ask for and the changelog does not list; sync daemons, servers or container mounts running as another user lose read access. Open with `0o666` so the umask yields 0644 and update the `0o600` expectation at test_create_zettel_use_case.py:525. | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:73 | 2 | BLAKE, EVE |
| R7 | [2/5] | 🟡 | SKILL.md:73 and bim.rst:243 say "A failed create writes nothing", but the metadata read-back path returns `success=False` ("note saved at <path>, but metadata failed") after the file exists (pinned by test_create_note.py:520), so an agent following the skill retries and duplicates. Document the exception: an error starting with `note saved at` means the file exists, do not retry. | src/tools/bim/SKILL.md:73 | 5 | BOB, EVE |
| R8 | [2/5] | 🟡 | The serve `create_note` action deliberately does not forward `source`; the design said to forward `body`, `source` and `dry_run` with confinement. A source-only request creates an empty note. The CHANGELOG documents the choice and `test_create_note_action_forwards_scripting_params_but_not_source` pins it, a conservative, documented deviation. | src/tools/bim/commands/serve/_actions.py:73 | 3 | BOB, ALICE |
| R9 | [1/5] | 🟠 | Template destinations are not confined before writing: `folder: ../outside`, an absolute folder or a symlinked `contact/` places a note outside the vault; metadata validation happens after saving. Resolve and confine the destination before `mkdir` and the reservation (00119 scope). | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:64 | general | BOB |
| R10 | [1/5] | 🟠 | An invalid UTF-8 daily note makes the create return failure after saving the new note: `_after_save` catches only `OSError` while `UnicodeDecodeError` reaches the outer handler. Catch it as a post-save `metadata["errors"]` entry and continue the source cleanup (00120 scope). | src/tools/bim/commands/create_note/create_note.py:142 | general | BOB |
| R11 | [1/5] | 🟠 | Article originals are written to their final filename without failure cleanup: a write or close failure leaves a partial archive that blocks retries, because `archive_original` runs outside the rollback block (00120 scope). | src/tools/bim/shared/article_archive.py:40 | general | BOB |
| R12 | [1/5] | 🟠 | Concurrent daily-log updates can silently discard an entry: both processes read the same content, the last atomic replacement wins and both report `added` (00120 scope). | src/tools/bim/shared/vault_links.py:37 | general | BOB |
| R13 | [1/5] | 🟡 | Scope beyond PRD 00118: `--summary-file`, `--no-daily-log`, `--no-link-contacts`, the article archive path, the daily-log append, contact wikilinking, reserved-tag rejection, the `daily_log`/`linked_contacts`/`archive` metadata, the `daily_log`/`link_contacts`/`summary` params and the `file_stem == "slug"`/`folder` handling come from the sibling PRDs 00119/00120 on the same branch; a spec-only audit still counts them. | src/tools/bim/note_write_cli.py:94 | general | BLAKE |
| R14 | [1/5] | 🟡 | `execute` runs hooks between the reservation and `writer.save`; the 00118 text says hooks run after the save, with 00119 moving them. A hook that is slow or killed leaves a zero-byte `<id>.md` visible to vault scanners; a normal failure is cleaned up by the inode-checked unlink in `finally`, a SIGKILL is not. | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:93 | 2 | BLAKE |
| R15 | [1/5] | 🟡 | A template question named `tags` bypasses validation when `params.tags` is omitted: its extra answer or default enters `answers` unchecked. Apply the same normalization, grammar and reserved-tag checks to question-supplied tags. | src/tools/bim/commands/create_note/create_note.py:219 | 3 | BOB |
| R16 | [1/5] | 🟡 | The bundled article template is unusable from the TUI: creation requires the original text and a summary, and the TUI supplies neither (00120 scope). | src/tools/bim/tui/create_note.py:180 | general | BOB |
| R17 | [1/5] | 🟡 | Contact linking rewrites Markdown constructs promised to stay untouched: reference links such as `[Ada Lovelace][person]` and indented code are not protected spans (00120 scope). | src/tools/bim/shared/vault_links.py:18 | general | BOB |
| R18 | [1/5] | 🟡 | The wikilink is built with `relative_path[:-3]`; use `relative_path.removesuffix(".md")`. | src/tools/bim/commands/create_note/create_note.py:236 | 3 | CARL |
| R19 | [1/5] | ⚪ | `_trash_source` moves with `os.link` plus `unlink`, not a rename; on a filesystem without hard links the move fails after the note exists and the failure lands in `metadata["errors"]`, which the spec allows. | src/tools/bim/commands/create_note/create_note.py:249 | 3 | BLAKE |
| R20 | [1/5] | ⚪ | `CommandCreateNote.execute` catches only `OSError`, `ValueError` and `RuntimeError`; any other exception (repo parser, template build) reaches the user as a traceback instead of `{"error": ...}`, breaking the JSON contract on those paths. | src/tools/bim/commands/create_note/create_note.py:73 | 3 | BLAKE |
| R21 | [1/5] | ⚪ | A blank line between the two `### Changed` bullets splits the changelog list. | CHANGELOG.md:33 | 5 | EVE |
| R22 | [1/5] | ⚪ | `--json` "and nothing else" is tested only with the command mocked; the template loader logs a malformed user template with `logger.warning`, which reaches stderr through Python's last-resort handler when no handler is configured. Eve's check: place a YAML template with `file_stem: bogus` in the user templates dir, run `bim create -t note --title x --json 1>out.json 2>err.txt` against a scratch zettelkasten, confirm `out.json` is one JSON line and the warning is in `err.txt` (VERIFY item; not queued on a standalone run). | src/lib/buvis/pybase/zettel/infrastructure/persistence/template_loader.py:43 | 4 | EVE |
| R23 | [2/5] | 🟡 | 8 touched tests in this file pass against the pre-change code (`test_sets_id_from_dates_own_wall_clock` UTC and naive cases, `test_raises_on_invalid_date` and 2 more; fail-first replay); among them `test_raises_when_formatted_date_is_not_numeric`, which subclasses `datetime` with a fake `strftime` to reach the "Invalid ID format" branch that a real datetime can never hit, a mock-only path. Delete that test; the offset change itself is pinned by the `local-offset` and midnight cases, which fail at base. | tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py:51 | 1 | EVE, mech-check |
| R24 | [1/5] | 🟡 | 3 touched tests pass against the pre-change code: `test_raises_file_exists`, `test_cleanup_preserves_file_that_replaced_owned_placeholder` (fail-first replay). | tests/lib/zettel/application/test_create_zettel_use_case.py | 2 | mech-check |
| R25 | [1/5] | 🟡 | 5 touched tests pass against the pre-change code: `test_does_not_override_existing_date` (fail-first replay). | tests/lib/zettel/entities/zettel/fixers/test_set_default_date.py | 1 | mech-check |
| R26 | [1/5] | 🟡 | 2 touched tests pass against the pre-change code: `test_consistency_preserves_existing_utc_derived_id_with_non_utc_date` (fail-first replay). | tests/lib/zettel/entities/zettel/test_zettel_consistency_service.py | 1 | mech-check |
| R27 | [1/5] | 🟡 | 1 touched test passes against the pre-change code: `test_create_file_not_found` (fail-first replay). | tests/tools/bim/test_bim_cli_handlers.py | 4 | mech-check |
| R28 | [1/5] | 🟡 | 2 touched tests pass against the pre-change code: `test_list_templates`, `test_execute_file_not_found_calls_panic` (fail-first replay). | tests/tools/bim/test_create_note_cli_wiring.py | 3 | mech-check |
| R29 | [1/5] | 🟡 | 4 touched tests pass against the pre-change code: `test_import_existing_file`, `test_import_with_flags`, `test_import_multiple_scripted`, `test_import_multiple_interactive_errors` (fail-first replay). | tests/tools/bim/test_note_write_cli.py | 4 | mech-check |

## Consolidation notes

The canonical consolidation script produced 23 rows from the five outputs and merged three cross-reviewer paraphrases itself (R1, R2, the fstat row). The coordinator then folded Eve's FIX and VERIFY items in (her buckets carry no `[EVE]` issue lines) and merged five groups, renumbering: R2 (Eve's misfiled-tests item joins the file-size row), R3 (Bob, Carl and Alice on `test_cancel_exits`, Eve's FIX item and the tautological-shape mech line), R4 (Eve's exit-0 usage paths, Alice's untested `edit` exit and the exit-0 half of Blake's traceback finding, whose traceback half stays R20), R5 (Alice's fstat-raises placeholder, Carl's discarded fstat and Eve's close-retry simplification, one code region), R6 (Blake and Eve on the 0600 mode), R7 (Bob and Eve on the "writes nothing" claim), R8 (Bob's serve `source` finding and Alice's documented-deviation note), R23 (the test_set_default_id.py replay line carries Eve's mock-only test). The remaining six replay lines were absorbed as R24-R29 with `mech-check` as the finder; Eve's KNOWN bucket justifies each one (quoted under Dispositions). No ledger exists (cycle 1), so nothing was auto-dismissed.

## Dispositions

Coordinator recommendations; this standalone run creates no tasks.

- Fix: R6 (one mode argument; a user-visible regression confirmed live twice), R4 (the documented exit contract is only half true; `ctx.exit(1)` after the usage-failure `console.failure` calls and the missing `edit` test), R7 (one documented exception in SKILL.md and bim.rst prevents duplicate notes by retrying agents), R5 (simplify the close handling and pin the fstat-raises placeholder behaviour), R15 (validation gap at the CLI boundary), R20 (AGENTS.md forbids raw tracebacks reaching the user; a last-resort `except Exception` in the `--json` handler keeps the one-line contract), R23 (delete the mock-only test), R1, R2 (style limits shared with the other two cycles), R18 and R21 (trivial).
- Fix in the sibling cycles: R9 is 00119's R6; R10, R11, R12, R16 and R17 are 00120's R1, R9, R15, R6 and R12, where they carry higher consensus.
- Defer: R8 (conservative, documented deviation; revisit when serve gains source confinement), R22 (run Eve's check once; it is a verification, not a code change).
- Dismiss: R3 (pre-existing, untouched test; the same row appears in all three cycles), R13 (the three PRDs were implemented on one branch by design; the branch is the merge unit), R14 (00119's specification moves hooks before the save; the zero-byte placeholder under SIGKILL is the accepted cost of the exclusive reservation), R19 (spec-compliant per Eve's KNOWN item), R24-R29 (Eve's KNOWN bucket: each pins preserved behaviour the PRD requires, exhausted-budget raises, never deleting an unowned file, keeping an existing date, the `ValueError("Invalid date format")` contract, panic on a missing file, unchanged `import` behaviour; the behaviour changes themselves are pinned by `test_gives_up_after_five_attempts`, `test_save_failure_removes_owned_placeholder_after_hooks_ran`, `test_sets_local_date_without_microseconds`, the offset cases of the id test and test_bim_cli_handlers.py:318, which all fail at base).

## Alice

Alice's output (12 R verdicts, 6 issue lines). The implementation-aware prompt carried the 00118 design doc.

```text
[ALICE] 🟡 `create_note` (78 lines) and `_create_note_scripted` (84 lines) both exceed the 50-line limit. Split `_create_note_scripted` into body/summary input reading, params and command construction, and result rendering. Move the "scripted" flag computation in `create_note` into a small helper. | File: src/tools/bim/note_write_cli.py:114 | Task: general
[ALICE] 🟡 `tests/tools/bim/test_create_note.py` is 952 lines, over the 800-line limit. Split it by concern (for example tag/source/dry-run in one file, vault links and article workflow in another). | File: tests/tools/bim/test_create_note.py:1 | Task: general
[ALICE] 🟡 The new "exit 1 on failure" behaviour for `edit_note` has no test. The PRD premise only flipped the 7 existing `success=False` assertions, and none of those covers `edit`. Add a failed-result handler case asserting `exit_code == 1`. | File: src/tools/bim/note_write_cli.py:332 | Task: general
[ALICE] ⚪ If `os.fstat` on the reservation descriptor raises, `reservation` stays None. The finally block then leaves a zero-byte placeholder that this invocation created. It blocks that id until someone removes it. The test `test_inspection_failure_closes_reservation_and_skips_save_and_hooks` does not assert whether the placeholder remains. Pin the intended behaviour. | File: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:435 | Task: general
[ALICE] ⚪ The serve `create_note` action deliberately does not forward `source`. The design said to forward `body`, `source` and `dry_run` with confinement. The CHANGELOG documents the choice and a test pins it (`test_create_note_action_forwards_scripting_params_but_not_source`), so this is a conservative, documented deviation. | File: src/tools/bim/commands/serve/_actions.py:1886 | Task: general
[ALICE] ⚪ [MECH] `test_cancel_exits` has no assertion. It is not touched by this diff, so it is pre-existing. | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
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
R12: fail
R13: fail

## Blake

Blind lens, PRD-only. Blake verified the fixers, `prepare`, the retry budget, tag validation, source confinement, dry run, `--json`, the `ctx.exit(1)` sites, both adapter call sites, docs and tests, and ran the PRD's exit criteria live in a scratch vault (details in `docs/dev/tmp/blake-output-20261109-00118.txt`).

```text
[BLAKE] 🟠 Notes created by `bim create` are written with mode 0600 instead of 0644. `execute` reserves the path with `os.open(path, O_CREAT|O_EXCL|O_WRONLY, 0o600)`. `atomic_write` then keeps the existing file's mode (src/lib/buvis/pybase/filesystem/atomic_write.py:36), so the 0o644 default never applies. I confirmed it in a scratch vault: `-rw------- ... 20261109140822.md`. Before, a new note got 0644. Other users or services that read the vault (a sync daemon, a web server, a container bind mount) lose access. The spec names no mode. Dropping the explicit 0o600, so the umask applies, would fix it. | File: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:73 | Task: Exclusive reservation
[BLAKE] 🟡 Scope creep beyond PRD 00118. The CLI adds `--summary-file`, `--no-daily-log` and `--no-link-contacts`. The command adds an `article` template path with archive handling, daily-log append, contact wikilinking, reserved-tag rejection and `daily_log`/`linked_contacts`/`archive` metadata. `CreateNoteParams` gains `daily_log`, `link_contacts` and `summary`. The use case adds `file_stem == "slug"` and `folder` handling that disables the collision retry. None of it is in this spec. It appears to come from sibling PRDs 00119/00120 on the same branch, and the changelog confirms that. A spec-only audit still counts it. | File: src/tools/bim/note_write_cli.py:94 | Task: general
[BLAKE] 🟡 `execute` runs hooks between the reservation and `writer.save`. The spec says hooks run after the save, with 00119 moving them. A hook that is slow or killed leaves a zero-byte `<id>.md` visible to vault scanners. A normal failure is cleaned up by the inode-checked unlink in `finally`, but a SIGKILL is not. This is likely the later PRD's intended behaviour, but it differs from the 00118 text. | File: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:93 | Task: Exclusive reservation
[BLAKE] ⚪ `_trash_source` moves with `os.link` plus `unlink`, not a rename. On a filesystem without hard-link support the move fails after the note exists. The source stays in the inbox and the failure goes to `metadata["errors"]`. The spec allows reporting a failed move that way, so this is minor. | File: src/tools/bim/commands/create_note/create_note.py:249 | Task: Body and source input
[BLAKE] ⚪ `CommandCreateNote.execute` catches only OSError, ValueError and RuntimeError. Any other exception, for example from the repo parser or a hook, reaches the user as a traceback and not as `{"error": ...}`. That breaks the "JSON and nothing else" contract for those paths. The non-CommandResult early exits in the other handlers (e.g. "TUI edit requires a single path", `resolve_paths` returning None) still exit 0. The spec covers only `CommandResult` failures. | File: src/tools/bim/commands/create_note/create_note.py:73 | Task: general
```

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
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

Codex, inlined prompt (review context with the design doc, full diff, consensus rubric, doubt appendix and de-slop lens). Twelve FIX items, no VERIFY or KNOWN items.

```text
[BOB] 🟠 Template destinations are not confined before writing: `folder: ../outside`, an absolute folder, or a symlinked `contact/` can place notes outside the vault; metadata validation happens after saving. Resolve and validate the destination before directory creation or reservation. | File: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:64 | Task: general
[BOB] 🟠 An invalid UTF-8 daily note causes creation to return failure after saving the new note: `_after_save` catches only `OSError`, while `UnicodeDecodeError` reaches the outer failure handler. Catch decoding failures as post-save `metadata["errors"]` and continue source cleanup; add a regression test. | File: src/tools/bim/commands/create_note/create_note.py:142 | Task: general
[BOB] 🟠 Article originals are written directly to their final filename without atomic persistence or failure cleanup. A write/close failure leaves a partial archive that blocks retries, because `archive_original` runs outside the rollback block. Use exclusive reservation plus atomic persistence and owned-file cleanup. | File: src/tools/bim/shared/article_archive.py:40 | Task: general
[BOB] 🟠 Concurrent daily-log updates can silently discard an entry: both processes read the same content, then the last atomic replacement wins while both report `added`. Serialize the complete read-modify-write operation with a cross-process lock and test overlapping updates. | File: src/tools/bim/shared/vault_links.py:37 | Task: general
[BOB] 🟡 The serve adapter silently discards `source`, contrary to the supplied design's confined-source forwarding requirement. A source-only request can successfully create an empty note. Confine and forward the source through the shared command, with an adapter regression test. | File: src/tools/bim/commands/serve/_actions.py:73 | Task: general
[BOB] 🟡 A template question named `tags` bypasses validation when `params.tags` is omitted: its extra answer or default enters `answers` unchecked. Apply the same normalization, grammar and reserved-tag checks to question-supplied tags. | File: src/tools/bim/commands/create_note/create_note.py:219 | Task: general
[BOB] 🟡 The bundled article template is unusable from the TUI: creation now requires original text and summary, but the TUI supplies neither. Add those inputs to the shared parameter flow so article creation remains available across interfaces. | File: src/tools/bim/tui/create_note.py:180 | Task: general
[BOB] 🟡 Contact linking rewrites Markdown constructs promised to remain untouched: `[Ada Lovelace][person]` and indented code are not protected. Extend protected-span detection for reference links and indented code, with preservation tests. | File: src/tools/bim/shared/vault_links.py:18 | Task: general
[BOB] 🟡 "A failed create writes nothing" contradicts the implemented and tested metadata-readback failure, which retains the saved note. Document the path-bearing failure and instruct consumers to inspect that note before retrying. | File: src/tools/bim/SKILL.md:76 | Task: general
[BOB] 🟡 The changed CLI functions exceed the 50-line limit: `create_note` is 78 lines and `_create_note_scripted` is 84. Extract file-input adaptation and result rendering into focused helpers while preserving validation order and JSON handling. | File: src/tools/bim/note_write_cli.py:114 | Task: general
[BOB] 🟡 The expanded command test file reaches 952 lines, exceeding the 800-line limit. Move article-workflow and vault-link integration tests into separate modules with shared fixtures. | File: tests/tools/bim/test_create_note.py:732 | Task: general
[BOB] 🟡 The supplied mechanical check identifies `test_cancel_exits` as assertion-free; it does not verify cancellation. Assert that cancellation exits the app and performs no creation. | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
```

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via copilot (gemini-3.8-flash). No frontend surface in this diff, reviewed as a generalist.

```text
[CARL] 🟡 test_cancel_exits has no assertion: it only proves the code does not raise | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
[CARL] 🟡 Function create_note exceeds 50-line limit (78 lines) | File: src/tools/bim/note_write_cli.py:114 | Task: 4
[CARL] 🟡 Function _create_note_scripted exceeds 50-line limit (84 lines) | File: src/tools/bim/note_write_cli.py:201 | Task: 4
[CARL] 🟡 File size exceeds 800-line limit (952 lines); split TestVaultLinks and TestArticleWorkflow into separate test modules | File: tests/tools/bim/test_create_note.py:1 | Task: 3
[CARL] 🟡 Discarded return value of os.fstat in BaseException handler prevents reservation cleanup if interrupted | File: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:96 | Task: 2
[CARL] 🟡 Use relative_path.removesuffix('.md') instead of slicing relative_path[:-3] when building wikilink | File: src/tools/bim/commands/create_note/create_note.py:236 | Task: 3
```

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: fail
R13: fail

## Eve

Doubt lens (fable), fifth lens because codex implemented tasks 1-3. Eve verified the PRD's exit criteria live in a scratch vault (local-time id, the `{"error": ...}` line and exit 1, `--source` with `--dry-run`, the invalid-tag failure, two same-second creates one sleep apart) and confirmed the compiled `_core` extension postdates the Rust parity change. Eight FIX items, one VERIFY item, twelve KNOWN items (full text in `docs/dev/tmp/eve-output-20261109-00118.txt`).

FIX (summarised; file and line in the table rows named): the 0600 note mode (R6); usage failures that still exit 0 despite the docs (R4); the "A failed create writes nothing" claim (R7); the assertion-less `test_cancel_exits` (R3); the mock-only `test_raises_when_formatted_date_is_not_numeric` (R23); the unnecessary `except BaseException` close retry (R5); the 953-line test file with two misfiled tests (R2); the blank line splitting the Changed bullets (R21).

VERIFY: the `--json` one-line contract against a template loader warning (R22; the exact check is in the row).

KNOWN (out of scope with justification): the TUI preview's own default-tag merge is 00119's and needs a TUI design change; the lint-suppression comment on `CommandCreateNote.__init__` needs a `VaultPaths` grouping across the three call sites; the Rust `date_from_filename` DST spring-forward gap is a once-a-year effect the PRD accepts under Risks; `--dry-run` inherits the collision wait because the PRD says it calls `prepare`; the `os.link` trash move matches the PRD's "reported in errors, not raised"; and one justification per fail-first replay line (quoted under Dispositions).

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Verdict: 29 findings

Tests: 7159 passed, 0 failed, 17 skipped (suite run this cycle)
