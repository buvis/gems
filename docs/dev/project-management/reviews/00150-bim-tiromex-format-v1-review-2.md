---
prd: docs/dev/project-management/prds/wip/00150-bim-tiromex-format-v1.md
review: 2
date: 2026-11-17
head_sha: d1c4d010135a01e51e2ae63b8e40065790c5db5a
codex_thread_id: 01a1e5a0-f6f6-7ce0-a3e3-7abe16d5fb9d
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 2606256b
  carl: 548ca4e0
---

# Review: 00150-bim-tiromex-format-v1

Diff range: `5b9f8587985a7252b665631f4daff03230ae1af2..d1c4d010135a01e51e2ae63b8e40065790c5db5a`

codex_rung_guard: not fired

Autopilot run, cycle 2, incremental review of the cycle 1 rework (tasks 9 to 12, eight commits since review 1). Interactive session (no `$_AUTOPILOT_LOOP`), so no Watcher was dispatched. Consensus engine: legacy. Pack: ok. Bob ran on codex with the inlined prompt (227 KB) and resumed his cycle 1 thread; his dispatch row was opened by `review-stage` on the staged render, so its `prompt_bytes` is too low. Carl ran on copilot, model gemini-3.8-flash. Consolidation: the canonical script ran with the ledger filter for Blake. No checks file exists for cycle 1, so nothing was carried forward.

All six findings that got rework in cycle 1 (R1, R2, R3, R4, R10, R13 of review 1) are resolved. Alice checked each one in the code and with the touched tests.

Coordinator notes:

- Mechanical test checks. The fail-first replay ran 32 touched tests against base `5b9f8587985a`: 15 failed there and 17 passed. The 15 are the new behaviour pins (9 help tests, 2 scalar `doubts` values, 2 new `test_bad_source` values, 2 mocked resolve errors). The line for `tests/tools/bim/tx/test_cli.py` is folded into R2 (`mech-check` added as finder); its other passing tests are the hardened bad-choices test, whose click diagnostic existed before the rework, and the choice-list test of a behaviour-preserving refactor. The line for `tests/tools/bim/tx/test_scope.py` is folded into R3. The lines for `test_new_status.py` and `test_validator.py` are R7 and R8: the passing tests are sibling values of parametrized tests whose new values fail against base.
- R2 is refuted. The coordinator ran the probe of `tests/tools/bim/tx/test_cli.py:519` against the pre-rework `src/tools/bim` (exported from `5b9f8587` to the scratchpad and put on `PYTHONPATH`): it loads `buvis.pybase.zettel.infrastructure` modules, so the test fails on the old code. Without `PYTHONPATH` the subprocess loads `bim.tx_cli` from the reviewed checkout. The replay line is an artifact: the test's subprocess does not get pytest's `pythonpath` setting, so in the replay worktree it loaded the installed checkout, not the base overlay. Alice made the same check on her own.
- R1 reproduces. In a scratch vault, `bim tx new --title` with the value `a`, newline, `---`, newline, `# b` exits 0 and writes a note whose body holds `# A`, a `---` line and `# b`; `bim tx validate` then reports the folder clean, because the note is a plain note.
- R3: Alice cited line 707; the file has 550 lines and the test is at line 197. The File cell is corrected.
- R4 is confirmed by reading the spec lines 378 and 458.
- Verification-check queue: not written. Bob's VERIFY item (R2) names a multi-step check and no single runnable command (not queued: command shape), and `agents/bob.md` defines no queue source. The coordinator ran the check instead (see R2 above).

## Review Summary

Reviewed: 12 completed tasks (4 of them cycle 1 rework)
PRDs checked: 00150-bim-tiromex-format-v1

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, resumed thread)
- Carl: ✅ Available (copilot, gemini-3.8-flash)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟡 | `bim tx new` with a non-concept note (no --concept-type) skips all validation because the note classifies as plain. A multi-line title such as "a\n---\n# b" is written as a malformed note: the title is a quoted multi-line scalar, and the body is "# A", "---", "# b", so the `---` line later parses as the backmatter separator. The draft-validate guard only protects concept, index and run notes. | src/tools/bim/commands/tx/new.py:95 | 6 | BLAKE |
| R2 | [1/4] | 🟡 | The import-weight regression passes against the eager-import baseline, according to replay. Check `bim.tx_cli.__file__` and the format module’s `__file__` in the subprocess against the reviewed checkout. Then rerun this test with both original module-level imports restored; it must fail. If it loads another checkout, explicitly set the subprocess import paths. | tests/tools/bim/tx/test_cli.py:519 | 11 | BOB, mech-check |
| R3 | [1/4] | ⚪ | `test_real_symlink_loop_never_escapes_as_another_error` is an either-or hedge: it returns on `ValueError`, otherwise asserts a lexical result. The venv runs Python 3.15, where `resolve()` does not raise on a loop, so the test passes against the pre-change code here (the replay flagged it too). The mocked-resolve test above it does pin the fix, so this is a weak extra guard rather than a gap. | tests/tools/bim/tx/test_scope.py:197 | 10 | ALICE, mech-check |
| R4 | [1/4] | ⚪ | The format spec says `source-shape` fails when there is "no `/` after the root name". The rework also rejects an empty root (`mirror:/x`) and an empty path part (`mirror:root/`), so the spec wording no longer describes the rule fully. Add "an empty root name or empty path" to the prose at line 376 or 378 and to the table row at line 458. | docs/reference/bim/tiromex/zettel-format-specification.md:378 | 10 | ALICE |
| R5 | [1/4] | ⚪ | `parse_note` cuts the body at the first line that is exactly `---`. A body that holds a horizontal rule or a fenced YAML sample ends there. The H1-count, empty-body and oversized-body checks then see only the text before the rule, so an oversized body can pass. | src/tools/bim/commands/tx/shared/format.py:159 | 2 | BLAKE |
| R6 | [1/4] | ⚪ | `_edges` compares the confined, symlink-resolved path with each note's unresolved vault-relative path. A note reached through an in-folder symlink alias can therefore miss a transitive-cycle edge. This is an edge case only, because `iter_note_files` keeps symlinked files whose targets stay inside the folder. | src/tools/bim/commands/tx/shared/validator.py:353 | 3 | BLAKE |
| R7 | [1/4] | 🟡 | [MECH] 2 touched test(s) pass against the pre-change code: test_malformed_doubts_value_counts_no_disagreement_and_does_not_crash | tests/tools/bim/tx/test_new_status.py | general | mech-check |
| R8 | [1/4] | 🟡 | [MECH] 7 touched test(s) pass against the pre-change code: test_bad_source +1 more | tests/tools/bim/tx/test_validator.py | general | mech-check |

### Auto-dismissed (ledger)

Blake findings that match a settled entry of the ledger (reason of the entry: single-voice). They are not in the table and create no task.

- BLAKE 🟡 `export-claims` does not preserve the source claim row contract. The port coerces `claim_id`, `statement`, `assent` and `lifecycle` with str() and drops claims whose id or statement is blank or None. The source emitted `claim["id"]` and `claim["statement"]` raw and kept any claim that had both keys, so an integer id (`id: 1`) now exports as "1", and a claim with a blank statement vanishes. The spec says the exported keys and contract are preserved. (File: src/tools/bim/commands/tx/shared/claims.py:47)
- BLAKE ⚪ The staleness boundary differs from the source. The port compares whole truncated days (`days > window`), while the source compared the exact age (`age > timedelta(days=window)`). A run 7d 23h ago reads as fresh in bim and stale in klyreon. (File: src/tools/bim/commands/tx/status.py:46)

## Alice

Ran the four touched test files (494 passed). Confirmed all six prior findings resolved and no regression from the rework. Checked on her own that the import-weight test fails against the old code. Findings: R3, R4.

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
R12: pass
R13: pass

## Blake

Blind (PRD-only). Ran the narrow acceptance suites (795 passed, plus the 90 integration tests) and drove the CLI on a scratch vault. No CRITICAL or HIGH. Findings: R1, R5, R6, and two rows the ledger filter dismissed (above).

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

Codex, inlined prompt, doubt and de-slop lens, resumed thread. FIX bucket: none. VERIFY bucket: R2 (not queued: command shape; the coordinator ran the check and it refutes the finding). KNOWN bucket: none.

R1: fail
R2: fail
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
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Copilot backend, model gemini-3.8-flash. Read the pack, the diff and the changed source; ran the tx tests, ruff, mypy and the bim and lib test markers. All clear: no issues found.

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

Verdict: 8 findings
Tests: 8006 passed, 0 failed, 17 skipped (reused from last-verification.json at d6d788f)
