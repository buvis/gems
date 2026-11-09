---
prd: docs/dev/project-management/prds/done/00119-bim-create-vault-templates-v1.md
review: 1
date: 2026-11-09
head_sha: 2f6aee1523307ab9504e118abc81f3c27760c67f
codex_thread_id: 01a1c06b-c782-76c2-950e-66007d0e7b9f
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: b44b2f7a
  carl: ee96ccf0
---

# Review: 00119-bim-create-vault-templates-v1

Diff range: `a087e05e3543d2b0c199fba8e0ccd5dabf5bf8ad..2f6aee1523307ab9504e118abc81f3c27760c67f`

codex_rung_guard: not fired

Standalone run (no `state.json`; the 202611090739 batch had closed). The three bim-create PRDs were moved to `prds/done/` before this review ran, so the review target was taken from `prds/done/`, not `prds/wip/`. The PRD was implemented attended on this branch together with 00118 and 00120 (one commit each plus a shared fix commit), so the reviewed diff is the whole branch scoped to code, tests and docs (`review-paths` marker: `AGENTS.md CHANGELOG.md README.md pyproject.toml docs/source src tests`; the autopilot store was excluded). Reviewers judged it against PRD 00119; findings that belong to 00118 or 00120 are marked in the dispositions. Tasks: none in a task store (standalone), the task table is empty. Pack: failed (engram not registered for this worktree). Fail-first replay: the path-scoped gather left no diff base in the scope line, so the replay ran by hand against `a087e05e` and its block was spliced into the staged context before the prompts were rendered. Carl ran on copilot, model gemini-3.8-flash. Blake's cycle-id 20261109-00119 disclosure: one scratch `bim create -t project` run without `BUVIS_BIM_PATH_DAILY` appended a log line to the real daily note `/Users/bob/bim/notes/calendar/daily/2026-11-09.md`; the line was removed again in this session and no probe note or project folder reached the real vault. Consolidation: the canonical script ran; the coordinator then merged five pairs of rows describing one defect in different words (listed under Consolidation notes).

## Review Summary

Reviewed: 0 tasks in a task store (standalone run; the work is the PRD 00119 commit `6a420eb6` plus the shared fix commits `98cf6d25` and `2f6aee15`)
PRDs checked: 00119-bim-create-vault-templates-v1 (00118 and 00120 reviewed in their own cycles)

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex)
- Carl: ✅ Available (copilot, gemini-3.8-flash)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | `create_note` (78 lines) and `_create_note_scripted` (84 lines) exceed the 50-line limit (mechanical facts). Split the stdin/file reading and the JSON/console reporting into helpers. | src/tools/bim/note_write_cli.py:201 | general | ALICE, BOB, CARL |
| R2 | [3/4] | 🟡 | `tests/tools/bim/test_create_note.py` is 952 lines, over the 800-line limit. Move `TestVaultLinks` and `TestArticleWorkflow` into their own modules. | tests/tools/bim/test_create_note.py:1 | general | ALICE, BOB, CARL |
| R3 | [3/4] | 🟡 | `test_cancel_exits` has no assertion; it only proves cancel does not raise. Pre-existing test, not touched by this diff. | tests/tools/bim/tui/test_create_note.py:73 | general | BOB, CARL, ALICE, mech-check |
| R4 | [2/4] | 🟡 | `--dry-run` skips template hooks, so the preview differs from the saved note: project shows an empty `parent` and no `resources`, illustrated-note shows a literal `{id}.svg`. bim.rst says "no hooks" but does not call out the preview deviation. | src/tools/bim/commands/create_note/create_note.py:98 | general | ALICE, BLAKE |
| R5 | [2/4] | 🟡 | The TUI preview re-implements the default-tag merge (`defaults + user tags not in defaults`) that `CommandCreateNote._answers` already does with lowercasing, `#` stripping and the reserved-tag check, so the two can drift and the preview can show a note that Create rejects. | src/tools/bim/tui/create_note.py:158 | general | ALICE, CARL |
| R6 | [2/4] | 🟠 | A template's `folder` is joined onto the zettelkasten path unvalidated: `..`, an absolute folder or a symlinked `contact/` places the note outside the vault, and creation writes before `_metadata` detects the escape. Resolve and confine the destination before `mkdir` and the reservation. Templates are trusted config, so the exposure is low. | src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:64 | general | BOB, ALICE |
| R7 | [2/4] | 🟡 | `slugify` strips diacritics with a character class holding raw, invisible combining characters (U+0300-U+036F). Use `̀-ͯ` escapes or `unicodedata.combining`, the idiom `vault_links._fold` already uses. | src/lib/buvis/pybase/formatting/string_operator/string_operator.py:118 | general | CARL, ALICE |
| R8 | [2/4] | ⚪ | `create_project_dir` now runs before `writer.save`, so a failed save leaves the empty `<path_projects>/<id>-<slug>` folder behind; the use case removes only its own placeholder file. | src/lib/buvis/pybase/zettel/infrastructure/persistence/template_loader.py:90 | general | ALICE, BLAKE |
| R9 | [1/4] | 🟡 | `docs/source/zettel.rst` still describes the old project template: line 64 "asks for dev type", line 267 `dev-type: spike`, line 354 `-a dev_type=spike` (fails today with `Missing required answer: deliverable`); the template-protocol table omits `folder`/`file_stem`/`default_tags`/`body_section`. The PRD's grep acceptance covered only SKILL.md and bim.rst. | docs/source/zettel.rst:354 | general | ALICE |
| R10 | [1/4] | 🟡 | No automated test creates a bundled vault template through `CommandCreateNote` with the real `discover_templates`, `run_template_hooks` and fixers, so the interplay with `fix_title_format` and `align_h1_to_title` is unpinned (contact, project and meeting-minutes scenarios were verified by hand only). | tests/tools/bim/test_create_note.py | general | ALICE |
| R11 | [1/4] | 🟡 | Required answers and declared choices are not validated when supplied: `deliverable=` (blank) and `location=online` are accepted. | src/tools/bim/commands/create_note/create_note.py:218 | general | BOB |
| R12 | [1/4] | 🟡 | A template question named `tags` bypasses normalization and the reserved-tag check when `--tags` is omitted. | src/tools/bim/commands/create_note/create_note.py:217 | general | BOB |
| R13 | [1/4] | 🟡 | Archive write or close failures leave a partial original at its final path, blocking retries; interruption during note creation bypasses the archive rollback (00120 scope). | src/tools/bim/shared/article_archive.py:42 | general | BOB |
| R14 | [1/4] | 🟡 | Concurrent creates can overwrite each other's daily-log entries: the read-modify-write is not serialized, only the replacement is atomic (00120 scope). | src/tools/bim/shared/vault_links.py:36 | general | BOB |
| R15 | [1/4] | 🟡 | Invalid UTF-8 in the daily note escapes the OSError-only handler and turns an already-saved create into a failure (00120 scope). | src/tools/bim/commands/create_note/create_note.py:142 | general | BOB |
| R16 | [1/4] | 🟡 | The PRR template writes `# {title}` instead of the PRD's `# PRR: {title}`; the implementation report labels this deliberate (the `align_h1_to_title` fixer would strip the prefix). | src/lib/buvis/pybase/zettel/domain/templates/problem_resolution_report.yaml:8 | general | BOB |
| R17 | [1/4] | ⚪ | A stray blank line splits the `### Changed` bullets in the changelog. | CHANGELOG.md:34 | general | ALICE |
| R18 | [1/4] | ⚪ | `book.yaml` writes `last-read: 9999-12-31` unquoted, so `yaml.safe_load` yields a date where the spec has the quoted string `"9999-12-31"`. | src/lib/buvis/pybase/zettel/domain/templates/book.yaml:9 | general | BLAKE |
| R19 | [1/4] | ⚪ | The meeting-minutes subject strip `\s*meeting minutes$` (case-insensitive) trims "Nonmeeting minutes" and leaves double spaces inside "meeting  minutes". | src/lib/buvis/pybase/zettel/domain/templates/meeting_minutes.py:36 | general | BLAKE |
| R20 | [1/4] | ⚪ | `YamlTemplate` rejects a `file_stem` other than `id`/`slug` and the loader skips the template with a warning; not in the PRD, a small defensive addition the changelog mentions. | src/lib/buvis/pybase/zettel/domain/templates/yaml_template.py:31 | general | BLAKE |
| R21 | [1/4] | ⚪ | Transcription fidelity of the prose bodies, the youtube iframe line and the Excalidraw JSON against the agent-skills template files is unverified (the blind reviewer had no network access). | N/A | general | BLAKE |
| R22 | [1/4] | 🟡 | 3 touched tests pass against the pre-change code: `test_raises_file_exists`, `test_cleanup_preserves_file_that_replaced_owned_placeholder` (fail-first replay). | tests/lib/zettel/application/test_create_zettel_use_case.py | general | mech-check |
| R23 | [1/4] | 🟡 | 5 touched tests pass against the pre-change code: `test_does_not_override_existing_date` (fail-first replay). | tests/lib/zettel/entities/zettel/fixers/test_set_default_date.py | general | mech-check |
| R24 | [1/4] | 🟡 | 8 touched tests pass against the pre-change code: `test_sets_id_from_dates_own_wall_clock`, `test_raises_on_invalid_date` and 2 more (fail-first replay). | tests/lib/zettel/entities/zettel/fixers/test_set_default_id.py | general | mech-check |
| R25 | [1/4] | 🟡 | 2 touched tests pass against the pre-change code: `test_consistency_preserves_existing_utc_derived_id_with_non_utc_date` (fail-first replay). | tests/lib/zettel/entities/zettel/test_zettel_consistency_service.py | general | mech-check |
| R26 | [1/4] | 🟡 | 1 touched test passes against the pre-change code: `test_create_file_not_found` (fail-first replay). | tests/tools/bim/test_bim_cli_handlers.py | general | mech-check |
| R27 | [1/4] | 🟡 | 2 touched tests pass against the pre-change code: `test_list_templates`, `test_execute_file_not_found_calls_panic` (fail-first replay). | tests/tools/bim/test_create_note_cli_wiring.py | general | mech-check |
| R28 | [1/4] | 🟡 | 4 touched tests pass against the pre-change code: `test_import_existing_file`, `test_import_with_flags`, `test_import_multiple_scripted`, `test_import_multiple_interactive_errors` (fail-first replay). | tests/tools/bim/test_note_write_cli.py | general | mech-check |

## Consolidation notes

The canonical consolidation script produced 28 rows from the four outputs. The coordinator then merged these pairs, each describing one defect in different words or at a neighbouring line, and renumbered: R3 (Bob, Carl and Alice on `test_cancel_exits`, plus the tautological-shape mech line), R5 (Alice and Carl on the TUI tag merge), R6 (Bob's use-case path escape and Alice's YAML `folder` check), R7 (Carl and Alice on the combining-mark regex; Carl cited line 118, Alice line 334, the regex lives at line 118), R8 (Alice and Blake on the project folder left behind). Blake's process disclosure about the stray daily-note line is not a defect in the work and sits in the top matter instead of the table; it is resolved. The seven fail-first replay lines were absorbed as R22-R28 with `mech-check` as the finder; none of the four reviewers raised them. No ledger exists (cycle 1), so nothing was auto-dismissed.

## Dispositions

Coordinator recommendations; this standalone run creates no tasks.

- Fix: R1, R2 (the style limits the project enforces; also raised in the 00118 and 00120 cycles), R6 (one `resolve()` and `is_relative_to` check before `mkdir` restores the confinement invariant; keep the severity, the exposure is trusted config), R9 (user-facing docs now fail when followed), R11 and R12 (validation gaps at the CLI boundary), R17 (trivial).
- Fix in the 00120 cycle: R13, R14, R15 belong to PRD 00120 and are recorded there with higher consensus.
- Defer: R4 (a preview without hook side effects is the documented design; a one-line doc note would close it), R5 (fold the TUI preview onto the command's tag normaliser when the TUI gains the 00120 inputs), R10 (one parametrised end-to-end test over contact, project and meeting-minutes; worth adding), R8, R18, R19, R20, R21 (low; R21 needs the upstream files).
- Dismiss: R3 (pre-existing test, untouched by this diff; the 00118 cycle carries the same row), R16 (the deviation is deliberate and documented in the implementation report: `align_h1_to_title` keeps the H1 equal to the title, so `# PRR:` would not survive `bim format`), R22-R28 (behaviour-preserving changes by design: existing tests touched for mock plumbing or sleep patches, parametrised cases whose UTC inputs give the same id in both code paths, and a cleanup guard that trivially holds when the base has no cleanup at all; `test_sets_id_from_dates_own_wall_clock` still fails at base for its `+02:00` case, which the replay's per-name dedup hides).

## Alice

Alice's output (12 R verdicts, 11 issue lines):

```text
[ALICE] 🟡 `_create_note_scripted` is 84 lines and `create_note` is 78 lines (computed facts), over the 50-line limit. Split the stdin/file reading and the JSON/console reporting into helpers; the 16 passthrough keywords suggest bundling them into one small dataclass | File: src/tools/bim/note_write_cli.py:201 | Task: general
[ALICE] 🟡 `tests/tools/bim/test_create_note.py` is now 952 lines, over the 800-line limit. Move the new `TestVaultLinks` and `TestArticleWorkflow` classes (the 00120 work) into their own module, e.g. `test_create_note_vault_links.py` | File: tests/tools/bim/test_create_note.py:1 | Task: general
[ALICE] 🟡 `docs/source/zettel.rst` still describes the old project template. Line 64 says project "asks for dev type", and line 267 shows `dev-type: spike`. The example at line 354, `bim create -t project ... -a dev_type=spike`, now fails with `Missing required answer: deliverable`. Update these to `deliverable`. The "Template protocol" table (around line 273) also omits the new optional `folder`/`file_stem`/`default_tags`/`body_section` attributes. The PRD's grep acceptance only covers SKILL.md and bim.rst, so this slipped through | File: docs/source/zettel.rst:354 | Task: general
[ALICE] 🟡 No automated test creates a bundled vault template through `CommandCreateNote` with the real `discover_templates`, `run_template_hooks` and fixers. The PRD's Critical Scenarios are contact `ada lovelace` -> `contact/ada-lovelace.md` with tag `person`, project -> `resources` in frontmatter plus backmatter order `parent, ticket, us, psd` plus the `<id>-probe` folder, and meeting `## Log` receiving the body. Each piece is unit-tested with fakes, so the interplay with `fix_title_format` and `align_h1_to_title` is unpinned. I ran all seven templates end to end by hand in scratch and the output was correct, so this is a test gap, not a bug. Add one parametrised end-to-end test over contact, project and meeting-minutes | File: tests/tools/bim/test_create_note.py | Task: general
[ALICE] 🟡 The TUI preview re-implements the default-tag merge: `defaults + user tags not in defaults`. `CommandCreateNote._answers` already does this, with lowercasing, `#` stripping and the reserved-tag check, so the two can drift. The preview skips the reserved-tag and validity checks, so it can show a note that Create then rejects. Extract one shared helper, or build the preview answers through the command, as the one-action-one-implementation invariant requires | File: src/tools/bim/tui/create_note.py:158 | Task: general
[ALICE] ⚪ The `create_project_dir` hook now runs before `writer.save`, so a save failure leaves an empty `<path_projects>/<id>-<slug>` folder behind. The use case removes only its own placeholder file. Accept this and document it, or note it as a known limit | File: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:445 | Task: general
[ALICE] ⚪ `--dry-run` does not run hooks, so the preview for project has an empty `parent` and no `resources`, and the illustrated-note preview shows a literal `{id}.svg`. It differs from the file a real create writes. bim.rst says "no hooks", but the preview deviation is not called out | File: src/tools/bim/commands/create_note/create_note.py:98 | Task: general
[ALICE] ⚪ A YAML template's `folder` is joined onto the zettelkasten path unvalidated, so `..` or an absolute path escapes the vault. Template files are trusted config, so this is low risk. A one-line check in `YamlTemplate.__init__` (relative, no `..`) would keep the confinement invariant uniform | File: src/lib/buvis/pybase/zettel/domain/templates/yaml_template.py:29 | Task: general
[ALICE] ⚪ `slugify` strips diacritics with a regex whose character class holds raw, invisible combining characters (U+0300-U+036F). `vault_links._fold` does the same job with `unicodedata.combining`. Use escapes, or `"".join(c for c in nfkd if not unicodedata.combining(c))`, for readability and a single idiom | File: src/lib/buvis/pybase/formatting/string_operator/string_operator.py:334 | Task: general
[ALICE] ⚪ [MECH] `test_cancel_exits` has no assertion; it only proves nothing raises. It was not changed by this diff. Assert `app.return_code`/exit state or delete it | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
[ALICE] ⚪ A stray blank line splits the `### Changed` bullets, so the `article` bullet sits apart from the others | File: CHANGELOG.md:34 | Task: general
```

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
R12: fail
R13: fail

## Blake

Blind lens, PRD-only. Blake ran every template in a scratch vault and verified the engine, slugify, template removal, docs and test presence (details in `docs/dev/tmp/blake-output-20261109-00119.txt`). Six findings; the process disclosure is recorded in the top matter.

```text
[BLAKE] 🟡 `--dry-run` skips template hooks, so the previewed content differs from what `execute` writes. An illustrated-note preview shows a literal `![Sk]({id}.svg)`. A project preview has an empty `parent`, no `resources` field and no `ticket`/`us`/`psd` lines. The PRD only moves hooks into `execute`, so this is a fidelity gap in a 00118 feature (preview), not a spec violation | File: src/tools/bim/commands/create_note/create_note.py:99 | Task: general
[BLAKE] ⚪ `book.yaml` writes `last-read: 9999-12-31` unquoted. `yaml.safe_load` turns that into a date object, where the spec writes a quoted string `"9999-12-31"`. The saved file looks the same, but the loaded type is a date | File: src/lib/buvis/pybase/zettel/domain/templates/book.yaml:9 | Task: general
[BLAKE] ⚪ The meeting-minutes subject strip uses `\s*meeting minutes$` (case-insensitive). A title like "Nonmeeting minutes" loses its tail. Double spaces inside "meeting  minutes" are not stripped | File: src/lib/buvis/pybase/zettel/domain/templates/meeting_minutes.py:36 | Task: general
[BLAKE] ⚪ `create_project_dir` creates the project folder before `writer.save`. If the save then fails, the reservation file is removed but the empty project folder stays | File: src/lib/buvis/pybase/zettel/infrastructure/persistence/template_loader.py:90 | Task: general
[BLAKE] ⚪ `YamlTemplate` raises on a `file_stem` other than `id` or `slug`, and the loader then skips the template with a warning. The PRD does not ask for this check; it is a small, defensive addition and the changelog mentions it | File: src/lib/buvis/pybase/zettel/domain/templates/yaml_template.py:31 | Task: general
[BLAKE] ⚪ I could not compare the prose bodies, the iframe line and the Excalidraw JSON with the upstream agent-skills template files. This audit had no network access. Transcription fidelity is unverified | File: N/A | Task: general
```

B1: pass
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

## Bob

Codex, inlined prompt (review context, full diff, consensus rubric, doubt appendix and de-slop lens). Ten FIX items, no VERIFY or KNOWN items.

```text
[BOB] 🟠 Template destinations can escape the zettelkasten through absolute folders, `..`, or a symlinked `contact/` directory. Creation writes before `_metadata` detects an escape. Resolve and confine the destination before creating directories or reserving files. | File: src/lib/buvis/pybase/zettel/application/use_cases/create_zettel_use_case.py:64 | Task: general
[BOB] 🟡 Required answers and choices are not validated when supplied: `deliverable=` and `location=online` are accepted. Validate nonblank required values and membership in declared choices before preparing the note. | File: src/tools/bim/commands/create_note/create_note.py:218 | Task: general
[BOB] 🟡 A template question named `tags` bypasses normalization and reserved-tag checks when `--tags` is omitted. Resolve question answers first, then validate and merge tags through one path. | File: src/tools/bim/commands/create_note/create_note.py:217 | Task: general
[BOB] 🟡 Archive write or close failures leave a partial original at its final path, blocking retries; interruption during note creation also bypasses archive rollback. Publish the complete archive atomically without overwriting, and clean owned artifacts on unsuccessful exits, including interruption. | File: src/tools/bim/shared/article_archive.py:42 | Task: general
[BOB] 🟡 Concurrent creates can overwrite each other's daily-log entries because atomic replacement does not serialize the read-modify-write operation. Lock the daily note across reading and replacement; test two competing appends. | File: src/tools/bim/shared/vault_links.py:36 | Task: general
[BOB] 🟡 Invalid UTF-8 in the daily note escapes the follow-up error handler and becomes an overall failure after the new note was saved. Catch UnicodeError alongside OSError and report it through metadata.errors. | File: src/tools/bim/commands/create_note/create_note.py:142 | Task: general
[BOB] 🟡 PRR emits `# {title}` instead of the required `# PRR: {title}`. Documentation labels this deliberate, but the supplied PRD does not accept this deviation. Preserve the required prefix through formatting and assert the saved heading. | File: src/lib/buvis/pybase/zettel/domain/templates/problem_resolution_report.yaml:8 | Task: general
[BOB] 🟡 The computed assertion-free `test_cancel_exits` does not establish cancellation. Assert that clicking Cancel exits the app and does not create a note. | File: tests/tools/bim/tui/test_create_note.py:73 | Task: general
[BOB] 🟡 `create_note` and `_create_note_scripted` span 78 and 84 lines respectively, exceeding the 50-line limit. Extract input-file loading and result rendering into focused helpers while preserving validation order and JSON behavior. | File: src/tools/bim/note_write_cli.py:114 | Task: general
[BOB] 🟡 The rewritten create-note test module contains 952 lines, exceeding the 800-line limit. Move article and vault-link scenarios into separate modules with shared fixtures. | File: tests/tools/bim/test_create_note.py:1 | Task: general
```

R1: fail
R2: fail
R3: pass
R4: pass
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
[CARL] 🟡 File size exceeds 800-line limit (952 lines); split TestVaultLinks and TestArticleWorkflow into separate test files | File: tests/tools/bim/test_create_note.py:1 | Task: general
[CARL] 🟡 Function create_note exceeds 50-line limit (78 lines) | File: src/tools/bim/note_write_cli.py:114 | Task: general
[CARL] 🟡 Function _create_note_scripted exceeds 50-line limit (84 lines) | File: src/tools/bim/note_write_cli.py:201 | Task: general
[CARL] 🟡 Replace unescaped combining mark regex literal with unicode escape [̀-ͯ] | File: src/lib/buvis/pybase/formatting/string_operator/string_operator.py:118 | Task: general
[CARL] 🟡 CreateNoteApp._update_preview duplicates CommandCreateNote default tag merge logic | File: src/tools/bim/tui/create_note.py:158 | Task: general
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

Verdict: 28 findings

Tests: 7159 passed, 0 failed, 17 skipped (reused from last-verification.json at 2f6aee1)
