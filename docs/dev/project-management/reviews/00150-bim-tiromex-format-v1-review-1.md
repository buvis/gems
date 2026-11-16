---
prd: docs/dev/project-management/prds/wip/00150-bim-tiromex-format-v1.md
review: 1
date: 2026-11-16
head_sha: 5b9f8587985a7252b665631f4daff03230ae1af2
codex_thread_id: 01a1e5a0-f6f6-7ce0-a3e3-7abe16d5fb9d
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: d8cbbcbd
  carl: 5f613833
---

# Review: 00150-bim-tiromex-format-v1

Diff range: `dcae39be19bc97a672b7c798fc5dcc309c7cd0dd..5b9f8587985a7252b665631f4daff03230ae1af2`

codex_rung_guard: not fired

Autopilot run, cycle 1, full review over the PRD's work range (`state.work_start_sha`). Interactive session (no `$_AUTOPILOT_LOOP`), so no Watcher was dispatched. Consensus engine: legacy. Pack: failed (engram: worktree not registered with gita); prompts carried `(no pack available this cycle)`. Bob ran on codex with the inlined prompt (501 KB). Carl ran on copilot, model gemini-3.8-flash. Consolidation: the canonical script ran; the coordinator then absorbed the mechanical test-check lines (R13 and R23 gained `mech-check`, R24 and R25 added). The coordinator confirmed R3 by reading `src/tools/bim/commands/tx/status.py:144`: `n.data.metadata.get("doubts") or []` is iterated without a list check, so `doubts: 42` raises `TypeError`.

Consolidation note: the script left three paraphrase pairs as separate rows although both name one defect at the same file and line. The coordinator merged them: R12 (BOB, eager format.py import) into R4; R15 (ALICE, symlink-loop RuntimeError in confine) into R10; R14 (ALICE, weak invalid-choice test) into R13. Refs R12, R14 and R15 are retired.

## Review Summary

Reviewed: 8 completed tasks
PRDs checked: 00150-bim-tiromex-format-v1

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex)
- Carl: ✅ Available (copilot, gemini-3.8-flash)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | `bim tx <cmd> --help` runs the `tx` group callback before Click builds the subcommand context; `bim tx validate --help` prints the stderr line "maintenance has never run". Help invocations should not warn or load settings; the test at tests/tools/bim/tx/test_cli.py:135 checks only options and exit code. | src/tools/bim/tx_cli.py:49 | 7 | ALICE, BLAKE |
| R2 | [2/4] | ⚪ | `_check_sources` accepts `mirror:/x` (empty root name) and `mirror:root/` (empty path part); the source-shape contract needs a root name before the first `/`. | src/tools/bim/commands/tx/shared/validator.py:255 | 3 | ALICE, BLAKE |
| R3 | [1/4] | 🟠 | A parseable note with `doubts: 42` or `doubts: true` crashes status: the disagreement counter iterates the scalar without checking its type. Guard for a list and add malformed-metadata status tests. | src/tools/bim/commands/tx/status.py:144 | 6 | BOB |
| R4 | [2/4] | 🟡 | `_ZETTEL_TYPES` is defined twice: a tuple at new.py:28 and a list at tx_cli.py:20, each filtering `wiki-article` out of `CONCEPT_NOTE_TYPES`. Keep one definition and reuse it. tx_cli.py:12 also imports format.py at module level to build the click.Choice lists, pulling the zettel parser and formatter into every `bim` start, while doc_cli.py and note_read_cli.py import their command code lazily; move the Choice values to a light constants module or build them lazily to keep the AGENTS.md lazy-import convention. | src/tools/bim/tx_cli.py:20 | 7 | ALICE, BOB |
| R5 | [1/4] | 🟡 | `export-claims` no longer emits the source values untouched: it coerces `claim_id`, `statement`, `assent` and `lifecycle` with `str()` and drops claims whose id or statement is blank, where the source exported any claim that had both keys. A YAML integer id `1` now exports as "1". The PRD says to preserve the export contract, so this is a small drift in the data shape. | src/tools/bim/commands/tx/shared/claims.py:40 | 3 | BLAKE |
| R6 | [1/4] | 🟡 | Null values bypass required validation: `assent: null`, `lifecycle: null`, `doubts: null`, and a doubt with `mode: null` evade their enum/list rules. Distinguish absent keys from present null values and test both cases. | src/tools/bim/commands/tx/shared/validator.py:197 | 3 | BOB |
| R7 | [1/4] | 🟡 | Non-string source values disappear through `sources()` before validation, so malformed values can pass without `source-shape`. Validate the raw source value and each list entry before extracting strings. | src/tools/bim/commands/tx/shared/validator.py:252 | 3 | BOB |
| R8 | [1/4] | 🟡 | `iter_note_files` checks resolved paths but returns unresolved aliases, contrary to the graph contract. An internal symlink duplicates exported claims and counts and can produce a false filename mismatch; graph keys also differ from resolved edges. Return sorted, deduplicated resolved paths and test internal aliases. | src/tools/bim/commands/tx/shared/paths.py:83 | 1 | BOB |
| R9 | [1/4] | 🟡 | Prune and corroboration checks compare literal link paths. A valid inbound link containing `./` or an internal symlink is missed, incorrectly reporting a linked note as a prune candidate. Resolve targets consistently with the validator before comparing note identities. | src/tools/bim/commands/tx/status.py:81 | 6 | BOB |
| R10 | [2/4] | 🟡 | A relation targeting a symlink loop escapes validation as `RuntimeError` or `OSError`: `confine` does not normalize resolution failures, while graph callers catch only `ValueError`. Convert these failures to contextual `ValueError` diagnostics and add a loop-target regression test. | src/tools/bim/commands/tx/shared/paths.py:63 | 1 | BOB, ALICE |
| R11 | [1/4] | 🟡 | Export destination expansion, resolution and `samefile` checks execute outside error handling. A symlink loop or inaccessible ancestor can raise instead of returning a failed `CommandResult`. Include destination preparation in the guarded operation and test failures before writing. | src/tools/bim/commands/tx/export_claims.py:39 | 5 | BOB |
| R13 | [2/4] | 🟡 | The invalid-choice integration test passes when the entire `tx` command is absent, as confirmed by replay: exit 2 and no files do not identify the intended rejection. Assert the specific invalid-choice or missing-title diagnostic for each case. | tests/tools/bim/tx/test_cli.py:210 | 7 | BOB, mech-check, ALICE |
| R16 | [1/4] | ⚪ | The staleness test changed: the source used `age > timedelta(days=window)`, the port uses `(now - last).days > window_days`, so a run 7d 5h ago counts as fresh now and stale in the source. | src/tools/bim/commands/tx/status.py:47 | 3 | BLAKE |
| R17 | [1/4] | ⚪ | The status metadata drops the source `sources` and `pending_sources` keys, and the first output lines changed from vault/zettels/sources to tiromex/notes; the PRD defers mirror pending counts to 00153 but also says to port the output keys. | src/tools/bim/commands/tx/status.py:160 | 3 | BLAKE |
| R18 | [1/4] | ⚪ | A new note ends at the H1 with no final `---` backmatter separator; the bim formatter omits it when there is no backmatter and the format spec documents this. PRD wording "final backmatter separator" is ambiguous; judged acceptable. | src/tools/bim/commands/tx/new.py:59 | 6 | BLAKE |
| R19 | [1/4] | ⚪ | `CommandTxNew` validates a draft from `prepare()`, then `execute()` builds the note again; id and date can differ by a second or after a collision bump. Risk judged negligible. | src/tools/bim/commands/tx/new.py:94 | 6 | BLAKE |
| R20 | [1/4] | ⚪ | Prune-candidate detection in `status` is O(n²) over notes because each concept note re-parses every other note's relations; no PRD performance requirement, but a large tiromex folder makes `status` slow. | src/tools/bim/commands/tx/status.py:74 | 3 | BLAKE |
| R21 | [1/4] | ⚪ | `claims: []` on a non-claim-bearing, non-aporia concept note now fails with `claims-count`; the source allowed it. Deliberate drift per "1-3 claims when present". | src/tools/bim/commands/tx/shared/validator.py:216 | 4 | BLAKE |
| R22 | [1/4] | ⚪ | Recursive cycle traversal can raise `RecursionError` on a sufficiently deep relation chain. This is explicitly recorded and the design mandates porting the source DFS unchanged; changing its traversal strategy exceeds that parity requirement. | src/tools/bim/commands/tx/shared/validator.py:319 | 3 | BOB |
| R23 | [1/4] | ⚪ | [MECH] `test_valid_dir_passes` has no assertion beyond successful return. It predates this change and tests directory validation, outside the additive stderr API scope. | tests/lib/pybase/adapters/test_console_adapter.py:448 | general | BOB, mech-check |
| R24 | [1/4] | 🟡 | [MECH] 3 touched test(s) pass against the pre-change code: test_warning_without_stderr_stays_on_stdout, test_failure_without_stderr_stays_on_stdout, test_stderr_is_keyword_only | tests/lib/pybase/adapters/test_console_adapter.py | general | mech-check |
| R25 | [1/4] | 🟡 | [MECH] 2 touched test(s) pass against the pre-change code: test_keeps_concept_fields_and_relations_and_is_idempotent | tests/tools/bim/test_format_note.py | general | mech-check |

## Alice

Ran the tx tests, `test_format_note.py` and `test_console_adapter.py` (774 passed), ruff and mypy on the touched code (clean). Found the implementation matches the design contracts for paths, format reader, validator table, the four commands, CLI rendering, the console stderr keyword and the AGENTS.md sentence. Findings: R1, R2, R4, R10 (merged R15), R13 (merged R14).

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

Blind (PRD-only). Ran the tx tests and `test_format_note.py` (709 passed) and drove the CLI on a scratch vault with isolated HOME and XDG_STATE_HOME. No CRITICAL or HIGH. No klyreon imports. Findings: R1, R2, R5, R16 to R21.

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

Codex, inlined prompt, doubt and de-slop lens. FIX bucket: R3, R4 (merged R12), R6 to R11, R13. VERIFY bucket: none (so no verification-check queue was written). KNOWN bucket: R22, R23 (and the matching `test_valid_file_passes` line at test_console_adapter.py:466, merged into R23).

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
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Copilot backend, model gemini-3.8-flash. Read the context, the changed source and tests, and ran the narrow tests, mypy, ruff and pre-commit. All clear: no issues found.

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

Verdict: 22 findings
Tests: 7985 passed, 0 failed, 17 skipped (suite run this cycle)
