---
prd: docs/dev/project-management/prds/done/00120-bim-create-vault-links-v1.md
review: 1
date: 2026-11-09
head_sha: 2f6aee1523307ab9504e118abc81f3c27760c67f
codex_thread_id: 01a1c06b-c782-7cc3-a895-a158915bceaf
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: d868b103
  carl: 653411a0
---

# Review: 00120-bim-create-vault-links-v1

Diff range: `a087e05e3543d2b0c199fba8e0ccd5dabf5bf8ad..2f6aee1523307ab9504e118abc81f3c27760c67f`

codex_rung_guard: not fired

Standalone run (no `state.json`; the 202611090739 batch had closed). The three bim-create PRDs were moved to `prds/done/` before this review ran, so the review target was taken from `prds/done/`, not `prds/wip/`. The PRD was implemented attended on this branch together with 00118 and 00119 (one commit each plus a shared fix commit), so the reviewed diff is the whole branch scoped to code, tests and docs (`review-paths` marker: `AGENTS.md CHANGELOG.md README.md pyproject.toml docs/source src tests`; the autopilot store was excluded). Reviewers judged it against PRD 00120. Tasks: none in a task store (standalone), the task table is empty. Pack: failed (engram not registered for this worktree). Fail-first replay: the path-scoped gather left no diff base in the scope line, so the replay ran by hand against `a087e05e` and its block was spliced into the staged context before the prompts were rendered. Carl ran on copilot, model gemini-3.8-flash. Consolidation: the canonical script ran; the coordinator then merged two pairs of rows describing one defect in different words (listed under Consolidation notes). The coordinator confirmed the top findings by reading the code: `_after_save` catches only `OSError` around the daily log, the archive rollback tuple is `(OSError, ValueError, RuntimeError)`, `archive_original` has no cleanup around its write, and `append_daily_log` finds `## Log` without fence tracking.

## Review Summary

Reviewed: 0 tasks in a task store (standalone run; the work is the PRD 00120 commit `d33f4855` plus the shared fix commits `98cf6d25` and `2f6aee15`)
PRDs checked: 00120-bim-create-vault-links-v1 (00118 and 00119 reviewed in their own cycles)

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex)
- Carl: ✅ Available (copilot, gemini-3.8-flash)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | Daily-log failures that are not `OSError` escape after the note is saved: `append_daily_log` reads with `read_text(encoding="utf-8")`, a non-UTF-8 daily note raises `UnicodeDecodeError` (a `ValueError`), `_after_save` catches only `OSError`, so `execute` returns `success=False` (exit 1) for a note that exists on disk, the source is not trashed and the promised `errors` entry is never written. Catch `(OSError, ValueError)` there and add a test with an invalid-UTF-8 daily note. | src/tools/bim/commands/create_note/create_note.py:142 | general | ALICE, BLAKE, BOB |
| R2 | [3/4] | 🟡 | `_create_note_scripted` (84 lines) and `create_note` (78 lines) exceed the 50-line limit (mechanical facts). Split input reading, params build and result rendering into helpers. | src/tools/bim/note_write_cli.py:201 | general | ALICE, BOB, CARL |
| R3 | [3/4] | 🟡 | `tests/tools/bim/test_create_note.py` is 952 lines, over the 800-line limit (about 340 before this branch). Split `TestVaultLinks` and `TestArticleWorkflow` into their own modules with shared fixtures. | tests/tools/bim/test_create_note.py:1 | general | ALICE, BOB, CARL |
| R4 | [3/4] | 🟠 | Archive rollback covers only `(OSError, ValueError, RuntimeError)`; any other exception, `KeyboardInterrupt` included, leaves an orphaned original under `path_articles` outside the vault. The PRD says a half-done article leaves no orphan and the AGENTS.md invariant requires release on any exit. Use `except BaseException` before the re-raise, or a `try/finally` guarded by a `created` flag, and test an interruption after archiving. | src/tools/bim/commands/create_note/create_note.py:119 | general | ALICE, BLAKE, BOB |
| R5 | [3/4] | 🟡 | `test_cancel_exits` has no assertion; it only proves cancel does not raise. Pre-existing test, not touched by this diff. | tests/tools/bim/tui/test_create_note.py:73 | general | ALICE, CARL, BOB, mech-check |
| R6 | [2/4] | 🟠 | Article creation is unusable from the TUI: the template offers only `web`, and the TUI supplies neither body nor summary, so Create always fails with "article needs --summary-file". The implementation report records this as a deferred pre-existing gap (00118's body is not reachable there either). | src/tools/bim/tui/create_note.py:180 | general | BOB, CARL |
| R7 | [2/4] | 🟡 | With `--body-file` or stdin the original is not frontmatter-stripped before archiving; only `--source` strips it. The PRD says "archived verbatim after frontmatter stripping" without limiting that to `--source`. `_clean` also trims leading blank lines and trailing whitespace from the "verbatim" original. | src/tools/bim/commands/create_note/create_note.py:171 | 1 | BLAKE, BOB |
| R8 | [2/4] | ⚪ | An article dry run does not check that the archive target is free or that the parent of `path_articles` exists, so a clean preview can precede a real run that fails with `FileExistsError` or "does not exist; set path_articles". | src/tools/bim/commands/create_note/create_note.py:98 | general | ALICE, BLAKE |
| R9 | [1/4] | 🟠 | Archive write failures leave a partial file that blocks retries with `FileExistsError`: the exclusive open succeeds before encoding, writing or closing can fail, and no cleanup surrounds those operations. Remove the owned archive on an unsuccessful write; test a write/close failure. | src/tools/bim/shared/article_archive.py:40 | general | BOB |
| R10 | [1/4] | 🟡 | No test covers the PRD's "an `OSError` goes to `metadata["errors"]`" path for the daily log, and no command-level test covers the article branch when the archive target already exists, `path_articles` is missing or its parent is missing (only `archive_original` is tested for the last two). | tests/tools/bim/test_create_note.py:731 | general | ALICE |
| R11 | [1/4] | 🟡 | `contact_names` calls `handle.read(2048)` on a text-mode handle, so it reads 2048 characters where the spec says the first 2048 bytes. | src/tools/bim/shared/vault_links.py:106 | 0 | BLAKE |
| R12 | [1/4] | 🟡 | Protected-span matching rewrites valid Markdown: double-backtick inline code containing a name protects only the empty delimiter pairs, and reference-style links (`[Ada Lovelace][person]`) are unprotected. | src/tools/bim/shared/vault_links.py:18 | general | BOB |
| R13 | [1/4] | 🟡 | Flow-list aliases are split inside quoted names: `aliases: ["Byron, Ada Lovelace"]` becomes two wrong aliases, so the intended name cannot match. | src/tools/bim/shared/vault_links.py:84 | general | BOB |
| R14 | [1/4] | 🟡 | Daily-log heading discovery accepts `## Log` inside fenced code and inserts the entry into that example instead of the real section; fence state is tracked only after the heading is found. | src/tools/bim/shared/vault_links.py:37 | general | BOB |
| R15 | [1/4] | 🟡 | Concurrent creates can lose daily-log entries: both callers read the same file, then the second atomic replacement discards the first caller's entry while both report `added`. Serialize the read-modify-write with a lock and test the interleaving. | src/tools/bim/shared/vault_links.py:35 | general | BOB |
| R16 | [1/4] | ⚪ | `append_daily_log` matches the heading with `re.fullmatch(r"## Log[ \t]*", line)` after `split("\n")`, so a CRLF daily note keeps a trailing `\r` on every line, `## Log` is not found and the misleading status "has no '## Log' section" is returned; the contact reader normalises CRLF, this function does not. | src/tools/bim/shared/vault_links.py:57 | general | ALICE |
| R17 | [1/4] | ⚪ | A blank line separates the `Changed` bullets in the changelog, breaking the one-bullet-per-line list style. | CHANGELOG.md:33 | general | ALICE |
| R18 | [1/4] | ⚪ | Files outside the PRD's list gained `path_daily`/`path_articles` plumbing (`serve_cli.py`, `serve/_app.py`, `serve/_security.py`, `serve/serve.py`, `params/serve.py`) and the serve create action accepts `summary`, `daily_log` and `link_contacts`; needed to wire the settings through serve, low-risk scope growth. | src/tools/bim/commands/serve/_actions.py:80 | 1 | BLAKE |
| R19 | [1/4] | 🟡 | 3 touched tests pass against the pre-change code: `test_raises_file_exists`, `test_cleanup_preserves_file_that_replaced_owned_placeholder` (fail-first replay). | tests/lib/zettel/application/test_create_zettel_use_case.py | general | mech-check |
| R20 | [1/4] | 🟡 | 5 touched tests pass against the pre-change code: `test_does_not_override_existing_date` (fail-first replay). | tests/lib/zettel/entities/zettel/fixers/test_set_default_date.py | general | mech-check |
| R21 | [1/4] | 🟡 | 8 touched tests pass against the pre-change code: `test_sets_id_from_dates_own_wall_clock`, `test_raises_on_invalid_date` and 2 more (fail-first replay). | tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py | general | mech-check |
| R22 | [1/4] | 🟡 | 2 touched tests pass against the pre-change code: `test_consistency_preserves_existing_utc_derived_id_with_non_utc_date` (fail-first replay). | tests/lib/zettel/entities/zettel/test_zettel_consistency_service.py | general | mech-check |
| R23 | [1/4] | 🟡 | 1 touched test passes against the pre-change code: `test_create_file_not_found` (fail-first replay). | tests/tools/bim/test_bim_cli_handlers.py | general | mech-check |
| R24 | [1/4] | 🟡 | 2 touched tests pass against the pre-change code: `test_list_templates`, `test_execute_file_not_found_calls_panic` (fail-first replay). | tests/tools/bim/test_create_note_cli_wiring.py | general | mech-check |
| R25 | [1/4] | 🟡 | 4 touched tests pass against the pre-change code: `test_import_existing_file`, `test_import_with_flags`, `test_import_multiple_scripted`, `test_import_multiple_interactive_errors` (fail-first replay). | tests/tools/bim/test_note_write_cli.py | general | mech-check |

## Consolidation notes

The canonical consolidation script produced 20 rows from the four outputs and merged four cross-reviewer paraphrases itself (R1, R2, R3, R6). The coordinator then merged two more pairs and renumbered: R4 (Alice and Blake at line 119 with Bob's 🟠 interruption finding at line 118, one defect; the fold takes Bob's severity) and R5 (Alice and Carl on `test_cancel_exits` with Bob's KNOWN item, plus the tautological-shape mech line). The seven fail-first replay lines were absorbed as R19-R25 with `mech-check` as the finder; Alice stated she did not raise them because they belong to behaviour-preserving 00118/00119 changes. No ledger exists (cycle 1), so nothing was auto-dismissed. Bob's VERIFY bucket was empty, so no verification-check queue was written.

## Dispositions

Coordinator recommendations; this standalone run creates no tasks.

- Fix: R1 (confirmed in code; one exception-tuple change plus a regression test), R4 and R9 (confirmed in code; together they make the article flow leave no orphan on any exit, which the PRD promises), R7 (strip one leading frontmatter block on both input routes and stop `_clean` trimming the archived original), R12, R13 and R14 (contact-link and daily-log parsing gaps in the ported helpers; each is a small guarded change with a regression case), R2 and R3 (style limits; shared with the other two cycles), R10 (tests for the error paths the PRD names), R17 (trivial).
- Defer: R6 (the TUI gap is recorded as deferred in the implementation report; the TUI needs body and summary inputs first, a scoped follow-up), R15 (a cross-process lock on the daily note is a design decision; two simultaneous creates by one vault owner are rare, document the limit if not fixed), R11 (characters versus bytes only matters for a frontmatter longer than 2 KB of multibyte text; align with the spec when touching the helper), R8 and R16 (low; R16 is a one-line `splitlines()` change worth folding into R14's fix), R18 (accepted scope growth, documented).
- Dismiss: R5 (pre-existing test, untouched by this diff; the 00118 cycle carries the same row), R19-R25 (behaviour-preserving changes by design: existing tests touched for mock plumbing or sleep patches, parametrised cases whose UTC inputs give the same id in both code paths, and a cleanup guard that trivially holds when the base has no cleanup at all).

## Alice

Alice's output (12 R verdicts, 9 issue lines). Alice did not raise the fail-first replay lines, treating them as passing by design for the 00118/00119 behaviour-preserving changes.

```text
[ALICE] 🟡 Daily-log failures that are not OSError escape after the note is saved. `append_daily_log` reads with `read_text(encoding="utf-8")`, so a non-UTF-8 daily note raises UnicodeDecodeError, which is a ValueError and not an OSError. `_after_save` catches only OSError, so the error reaches the outer handler in `execute`. The caller gets `success=False` (exit 1) for a note that exists on disk, the source is not moved to `.trash/`, and the `errors` entry the PRD promises is never written. Fix: catch `(OSError, ValueError)` in the daily-log try block, and add a test with an invalid-UTF-8 daily note. | File: src/tools/bim/commands/create_note/create_note.py:142 | Task: general
[ALICE] 🟡 Archive rollback covers only `(OSError, ValueError, RuntimeError)`. Any other exception, including KeyboardInterrupt, leaves an orphaned original under `path_articles` outside the vault. The AGENTS.md invariant "Claim/lifecycle release on any exit" requires release on any exit. The PRD says a half-done article leaves no orphan. Fix: use `except BaseException` before the `raise`, or a `try/finally` guarded by a `created` flag. | File: src/tools/bim/commands/create_note/create_note.py:119 | Task: general
[ALICE] 🟡 No test covers the PRD's "an `OSError` goes to `metadata["errors"]`" path for the daily log, so the `cannot add the daily note log entry` branch is untested. No command-level test covers the article branch when the archive target already exists (FileExistsError, no note written), a missing `path_articles`, or a missing parent of `path_articles` (ValueError). Only `archive_original` is tested for the last two. | File: tests/tools/bim/test_create_note.py:731 | Task: general
[ALICE] 🟡 `_create_note_scripted` is 84 lines and `create_note` is 78 lines, against the 50-line limit (per the mechanical facts). The nested `fail` and `report_success` helpers, the input reading, the params build and the result rendering can be split into helpers such as `_read_inputs(body_file, summary_file)` and `_render_create_result(...)`. | File: src/tools/bim/note_write_cli.py:201 | Task: general
[ALICE] 🟡 `tests/tools/bim/test_create_note.py` is 952 lines, over the 800-line limit. It was about 340 lines before this branch. Split it, for example `test_create_note_vault_links.py` and `test_create_note_article.py` for `TestVaultLinks` and `TestArticleWorkflow`, with the shared fixtures in a conftest. | File: tests/tools/bim/test_create_note.py:1 | Task: general
[ALICE] ⚪ `append_daily_log` matches the heading with `re.fullmatch(r"## Log[ \t]*", line)` after `split("\n")`. A CRLF daily note leaves a trailing `\r` on each line, so `## Log` is not found and the result is the misleading status "has no '## Log' section". The inserted entry would also use LF. The contact reader normalises CRLF, but this function does not. | File: src/tools/bim/shared/vault_links.py:57 | Task: general
[ALICE] ⚪ `test_cancel_exits` has no assertion (the MECH shape block flags it). It only proves the cancel action does not raise. | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
[ALICE] ⚪ The dry run for an article does not check that the archive target is free or that the parent of `path_articles` exists. `bim create -t article --dry-run` can report a clean preview that the real run rejects with FileExistsError or "does not exist; set path_articles". | File: src/tools/bim/commands/create_note/create_note.py:98 | Task: general
[ALICE] ⚪ In CHANGELOG.md a blank line separates the `Changed` bullets, which breaks the one-bullet-per-line list style used elsewhere in the file. | File: CHANGELOG.md:33 | Task: general
```

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail

## Blake

Blind lens, PRD-only. Blake ran the PRD's narrow suite (115 passed) and read every spec item into the code: the four helpers, `archive_original` with the exclusive open and sanitiser, `ArticleTemplate`, the two settings, the new params, the archive-note-trash order, the `--summary-file` rejection, the two flags and both adapter call sites; docs and changelog match (details in `docs/dev/tmp/blake-output-20261109-00120.txt`).

```text
[BLAKE] 🟡 `append_daily_log` reads the daily note with `read_text(encoding="utf-8")` and only OSError is caught around it. A non-UTF-8 daily note raises UnicodeDecodeError (a ValueError), which `execute` turns into a failed result after the note was already saved. The spec says problems at this step go to `metadata["errors"]` | File: src/tools/bim/commands/create_note/create_note.py:142 | Task: 1
[BLAKE] 🟡 `_create` unlinks the archive only for OSError, ValueError and RuntimeError from `use_case.execute`. Any other exception (a hook raising a different type, or KeyboardInterrupt) leaves an orphan archive file. The spec says the archive is unlinked whenever note creation fails | File: src/tools/bim/commands/create_note/create_note.py:119 | Task: 1
[BLAKE] 🟡 `contact_names` calls `handle.read(2048)` on a text-mode handle, so it reads 2048 characters. The spec says the first 2048 bytes. Files with multibyte names can read past the byte limit | File: src/tools/bim/shared/vault_links.py:106 | Task: 0
[BLAKE] ⚪ With `--body-file` or stdin, the original is not frontmatter-stripped before archiving. Only `--source` strips frontmatter. The spec says "archived verbatim after frontmatter stripping" without limiting this to `--source`. The `_clean` call also trims leading blank lines and trailing whitespace | File: src/tools/bim/commands/create_note/create_note.py:171 | Task: 1
[BLAKE] ⚪ A dry run of an article does not run the `path_articles` parent-exists check, so it can report success for a real run that would fail with "<parent> does not exist; set path_articles" | File: src/tools/bim/commands/create_note/create_note.py:98 | Task: 1
[BLAKE] ⚪ Extras outside the PRD's file list: `serve_cli.py`, `serve/_app.py`, `serve/_security.py`, `serve/serve.py` and `params/serve.py` gained `path_daily` and `path_articles` plumbing. The serve create action accepts `summary`, `daily_log` and `link_contacts` arguments. This is needed to wire the settings through serve, so it is low-risk scope growth | File: src/tools/bim/commands/serve/_actions.py:80 | Task: 1
```

B1: pass
B2: pass
B3: pass
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Codex, inlined prompt (review context, full diff, consensus rubric, doubt appendix and de-slop lens). Eleven FIX items, no VERIFY items, one KNOWN item.

```text
[BOB] 🟠 Archive write failures leave a partial file that blocks retries with FileExistsError. The exclusive open succeeds before encoding, writing, or closing can fail, and no cleanup surrounds these operations. Remove the owned archive on unsuccessful completion; test a write/close failure. | File: src/tools/bim/shared/article_archive.py:40 | Task: general
[BOB] 🟠 Interrupted note creation leaves an orphan archive. KeyboardInterrupt during collision retries, hooks, or saving bypasses the rollback exception tuple. Use failure cleanup covering BaseException while preserving the original exception; test interruption after archiving. | File: src/tools/bim/commands/create_note/create_note.py:118 | Task: general
[BOB] 🟡 Article originals supplied through --body-file retain frontmatter: stripping occurs only in the source branch. Also, _clean removes original whitespace despite the verbatim requirement. Strip one leading frontmatter block consistently for both input routes and preserve the remaining original text. | File: src/tools/bim/commands/create_note/create_note.py:171 | Task: general
[BOB] 🟠 Article creation is unusable from the TUI. The template offers only web, and the TUI supplies neither body nor summary, so Create always fails with "article needs --summary-file." Add original and summary inputs and forward them through CreateNoteParams. | File: src/tools/bim/tui/create_note.py:180 | Task: general
[BOB] 🟡 Protected-span matching rewrites valid Markdown code and links. For example, double-backtick inline code containing Ada Lovelace protects only the empty delimiter pairs; reference-style links are unprotected too. Recognize matching code delimiters and reference links before selecting mentions, with regression cases for both. | File: src/tools/bim/shared/vault_links.py:18 | Task: general
[BOB] 🟡 Flow-list aliases are split inside quoted names. aliases: ["Byron, Ada Lovelace"] becomes two incorrect aliases, so the intended name cannot match. Parse quoted flow lists with the YAML parser while retaining comma splitting for the explicitly supported scalar format. | File: src/tools/bim/shared/vault_links.py:84 | Task: general
[BOB] 🟡 Daily-log heading discovery accepts "## Log" inside fenced code and inserts the entry into that example instead of the actual section. Track fence state while locating the heading as well as while finding its end. | File: src/tools/bim/shared/vault_links.py:37 | Task: general
[BOB] 🟡 Concurrent creates can lose daily-log entries: both callers can read the same file, then the second atomic replacement discards the first caller's entry. Serialize the complete read-modify-write operation with a shared lock and test this interleaving. | File: src/tools/bim/shared/vault_links.py:35 | Task: general
[BOB] 🟡 Invalid UTF-8 in the daily note turns an already-saved create into a failure. UnicodeDecodeError bypasses the local OSError handler, reaches execute's ValueError handler, and prevents source cleanup. Record decoding failures in metadata["errors"] and continue the post-save steps. | File: src/tools/bim/commands/create_note/create_note.py:140 | Task: general
[BOB] 🟡 The CLI functions exceed the 50-line limit: create_note is 78 lines and _create_note_scripted is 84, per the supplied measurements. Extract input-file loading and result rendering into focused helpers while preserving the JSON and exit-code behavior. | File: src/tools/bim/note_write_cli.py:114 | Task: general
[BOB] 🟡 test_create_note.py reaches 952 lines, exceeding the 800-line limit. Move the daily/contact integration cases and article workflow cases into dedicated test modules, sharing their existing fixtures. | File: tests/tools/bim/test_create_note.py:732 | Task: general
KNOWN: [BOB] 🟡 The supplied mechanical check identifies test_cancel_exits as assertion-free; it cannot establish that cancellation exits. Its body is unchanged and cancellation is outside this PRD, so this is an existing test limitation. | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
```

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
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

Gemini via copilot (gemini-3.8-flash). No frontend surface in this diff, reviewed as a generalist; Carl also ran the PRD's narrow suite and `cargo test`.

```text
[CARL] 🟡 test_cancel_exits has no assertion: it only proves the code does not raise | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
[CARL] 🟡 _create_note_scripted is 84 lines, exceeding the 50-line limit; extract parameter resolution to simplify | File: src/tools/bim/note_write_cli.py:201 | Task: general
[CARL] 🟡 create_note is 78 lines, exceeding the 50-line function limit | File: src/tools/bim/note_write_cli.py:114 | Task: general
[CARL] 🟡 test_create_note.py is 952 lines, exceeding the 800-line file limit; split article and vault links tests | File: tests/tools/bim/test_create_note.py:1 | Task: general
[CARL] 🟡 TUI enables Create button for article template despite missing required CLI-only summary and body files | File: src/tools/bim/tui/create_note.py:177 | Task: general
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

Verdict: 25 findings

Tests: 7159 passed, 0 failed, 17 skipped (reused from last-verification.json at 2f6aee1)
