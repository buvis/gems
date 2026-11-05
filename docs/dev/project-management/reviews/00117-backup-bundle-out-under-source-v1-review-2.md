---
prd: docs/dev/project-management/prds/wip/00117-backup-bundle-out-under-source-v1.md
review: 2
date: 2026-11-05
head_sha: 70394a1abc69899c1af9ba0c82323df7aa16c736
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
dispatch_rows:
  bob: f4d57cb9
---

# Review: 00117-backup-bundle-out-under-source-v1

Diff range: `5ae5c53e49ad95d94562b60df99aa272e0772cc5..70394a1abc69899c1af9ba0c82323df7aa16c736`

codex_rung_guard: not fired
provider_review_guard: satisfied
autocodex_alice_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c2-alice-anthropic.txt.receipt.json
autocodex_alice_openai_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c2-alice-openai-retry.txt.receipt.json
autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c2-blake-anthropic.txt.receipt.json
autocodex_blake_openai_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c2-blake-openai-retry.txt.receipt.json
autocodex_bob_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c2-bob-anthropic.txt.receipt.json
autocodex_bob_openai_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c2-bob-openai.txt.receipt.json

The model-provider guard supersedes the legacy implementor guard. Eve did not run.
Both complete provider rosters reviewed the entire PRD change, including rework.
Anthropic used Kiro with observed Claude Opus 5.5 at xhigh; OpenAI used fresh Codex gpt-6.1-sol sessions with high effort requested by the helper.
All raw model, effort, session and tool evidence remains in the receipt-bound logs.
Carl: not invoked; no frontend changes.

## Review Summary

Reviewed both completed tasks. Implementation provenance is mixed Anthropic/OpenAI, verified against raw contributing worker logs, dispatches and commits. Every roster invocation was fresh and isolated.
Blake received only the PRD and gate evidence. Alice received implementation context and the complete consensus rubric. Bob received the context, full PRD-scoped diff, complete consensus rubric, doubt appendix and de-slop lens inline.
The original work range remains unchanged. PRD source, tests, docs and changelog were scoped into the diff; unrelated sysup/release and workflow evidence changes were excluded.
The initial OpenAI Alice and Blake prompts incorrectly applied the Kiro no-shell restriction to Codex. Both returned transport-blocked verdicts without inspecting code; neither certifies review. Each used its single fresh retry with Codex read-only exec inspection allowed. Their original outputs and receipts remain intact; the guard above references only the completed retries.
No Kiro permission denial occurred. No test or production repair ran in this session.

Staging emitted no mechanical tautology finding. Fail-first replay was skipped because its runner failed with a mise error; reviewers received this limitation. No previous-cycle verification queue exists. The full suite passed twice: staging lacked the parser-specific summary; the prescribed foreground verify fallback emitted the summary and recorded last-verification.json through the state CLI. Ruff and mypy passed.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Found By |
|-----|-----------|----------|-------|------|----------|
| R1 | [3/6] | 🟡 | Whole-tree containment and bundle source-equality now compare by filesystem identity (lines 298-299). On APFS, a case alias is now rejected: source `<tmp>/Src` with out `<tmp>/src/x.tar.gz` (old lexical guard allowed it). An out equal to a source alias now gets the source message. No test covers either branch. If both lines go back to lexical comparison, the suite still passes, because the permission test then raises in the item loop instead. Add case-alias cases for whole-tree and for bundle `out == source`, skipped like `_case_alias`. | src/tools/backup/capabilities/tar_archive.py:298 | ALICE_ANTHROPIC, BLAKE_ANTHROPIC, BOB_ANTHROPIC |
| R2 | [2/6] | 🟡 | Inode equality rejects valid hard-linked output names outside the selected items. For items ["a"], an external out hard-linked to source/a fails, although atomic replacement preserves a. Distinguish path aliases from distinct hard links and add coverage across both engines and all modes. | src/tools/backup/capabilities/tar_archive.py:308 | ALICE_OPENAI, BLAKE_OPENAI |
| R3 | [2/6] | ⚪ | The new default `selected: list[Path] | None = None` is never used, because both callers (lines 161, 362) pass the argument. Make it a required parameter. | src/tools/backup/capabilities/tar_archive.py:282 | ALICE_ANTHROPIC, BOB_ANTHROPIC |
| R4 | [2/6] | 🟡 | `test_invalid_items_take_precedence_over_output_containment` repeats `test_invalid_items_win_over_containment` (tests/tools/backup/test_bundle_items.py:471) and `test_invalid_items_win_over_containment_in_every_mode` (tests/tools/backup/test_plan_validation.py:375). It uses the same messages, engines and modes. Invalid items can never reach the item branch, so putting `out` inside `Config` tests no new path. Delete it. | tests/tools/backup/test_bundle_case_containment.py:169 | ALICE_ANTHROPIC, BOB_ANTHROPIC |
| R5 | [2/6] | ⚪ | Some parametrizations repeat one code path. Both `error` values inject the same `lstat(out)` failure, and the `selected` value "Profiles" exercises the same path as "Config" (:78, :102). Drop the duplicates. | tests/tools/backup/test_bundle_case_containment.py:49 | ALICE_ANTHROPIC, BOB_ANTHROPIC |
| R6 | [1/6] | ⚪ | The CHANGELOG entry was written under `[Unreleased]` and then moved into `[0.17.0] - 2026-11-04` by the `v0.17.0` bump. The cycle-2 fixes came after that release: case-alias outputs inside a selected item are now rejected, and output identity errors are reported as failures. `[Unreleased]` is empty, so these user-visible fixes have no entry. The 0.17.0 line claims inside-item outputs always fail, but the shipped 0.17.0 code missed case aliases on case-insensitive filesystems. | CHANGELOG.md:8 | BLAKE_ANTHROPIC |
| R7 | [1/6] | ⚪ | The docs give the wrong reason for refusing an `out` equal to a selected item. "because the archive would re-archive itself" does not fit that case, because writing `out` there would overwrite the selected item. The PRD also asked for one sentence; this paragraph has seven. | docs/source/tools/backup.rst:159 | BOB_ANTHROPIC |

## Consolidation notes

The canonical consolidation script processed all six successful outputs and ledger-dismissed OpenAI Blake's repeated released-changelog finding. The coordinator then split Bob's bundled duplicate-test observation into its two concrete defects and merged each with Alice's matching observation. This preserves both independent voices and avoids incorrectly discarding shared findings. Raw reviewer outputs are unchanged.

### Auto-dismissed (ledger)

OpenAI Blake's original Unreleased-location finding is settled: release 0.17.0 correctly moved the original entry. Anthropic Blake's post-release rework-entry finding is distinct and remains R6.

## Decision Gate

R1: tail sweep. Three voices identify missing case-alias tests for the source checks. Add both whole-tree and bundle source-equality cases across engines and modes.
R2: tail sweep. Two voices identify rejection of a distinct hard-linked output entry. Coordinator reproduced a valid outside output being refused by containment. Preserve case-alias safety while distinguishing separate directory entries, with regression coverage.
R3: tail sweep. Both callers supply selected; make the private parameter required.
R4: tail sweep. Both reviewers identify duplicate invalid-items precedence coverage; retain the existing coverage and remove the redundant test.
R5: tail sweep. Both reviewers identify duplicate parametrizations; retain meaningful coverage with one representative per identical path.
R6: discard under the source's mandatory single-voice Low rule; ledger records the post-release changelog observation separately.
R7: discard under the source's mandatory single-voice Low rule; ledger records the documentation rationale observation.

No unresolved Critical or High remains. Medium/Low findings do not block convergence. Five shared findings are queued for the normal work pipeline's Tail sweep, without another completion review or cycle increment.

## Verification

Full suite: 6660 passed, 16 skipped, 1 xfailed. Staging log: reports/00117-c2-full-suite.log. Structured fallback log: reports/00117-c2-structured-full-suite.log; record: reports/00117-c2-verification.json. All suite exits were zero. Isolated empty postup roots and cleared Git author variables avoid the previously recorded unrelated host failures.
Backup ruff passed; backup mypy passed for 11 source files. The hard-link probe used a temporary directory and left repository files unchanged.

## Alice

Both provider outputs follow.

### Anthropic

Prior cycle: both fix items are resolved. R1 is fixed because items are normalized once, at src/tools/backup/capabilities/tar_archive.py:160 and src/tools/backup/capabilities/tar_archive.py:362. R2 is fixed because `_same_path` compares by filesystem identity, and the case-alias tests run in the macOS CI tools job.

[ALICE] 🟡 Whole-tree containment and bundle source-equality now compare by filesystem identity (lines 298-299). On APFS, a case alias is now rejected: source `<tmp>/Src` with out `<tmp>/src/x.tar.gz` (old lexical guard allowed it). An out equal to a source alias now gets the source message. No test covers either branch. If both lines go back to lexical comparison, the suite still passes, because the permission test then raises in the item loop instead. Add case-alias cases for whole-tree and for bundle `out == source`, skipped like `_case_alias`. | File: src/tools/backup/capabilities/tar_archive.py:298 | Task: 2
[ALICE] 🟡 `test_invalid_items_take_precedence_over_output_containment` repeats `test_invalid_items_win_over_containment` (tests/tools/backup/test_bundle_items.py:471) and `test_invalid_items_win_over_containment_in_every_mode` (tests/tools/backup/test_plan_validation.py:375). It uses the same messages, engines and modes. Invalid items can never reach the item branch, so putting `out` inside `Config` tests no new path. Delete it. | File: tests/tools/backup/test_bundle_case_containment.py:169 | Task: 2
[ALICE] ⚪ Some parametrizations repeat one code path. Both `error` values inject the same `lstat(out)` failure, and the `selected` value "Profiles" exercises the same path as "Config" (:78, :102). Drop the duplicates. | File: tests/tools/backup/test_bundle_case_containment.py:49 | Task: 2
[ALICE] ⚪ The new default `selected: list[Path] | None = None` is never used, because both callers (lines 161, 362) pass the argument. Make it a required parameter. | File: src/tools/backup/capabilities/tar_archive.py:282 | Task: 2

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

### Openai

[ALICE] 🟡 Inode equality rejects valid hard-linked output names outside the selected items. For items ["a"], an external out hard-linked to source/a fails, although atomic replacement preserves a. Distinguish path aliases from distinct hard links and add coverage across both engines and all modes. | File: src/tools/backup/capabilities/tar_archive.py:308 | Task: 2

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Both provider outputs follow.

### Anthropic

[BLAKE] ⚪ The whole-tree containment branch changed behaviour in a mode the PRD says stays unchanged. Since the cycle-2 case-alias fix, both branches go through `_same_path`, which compares paths by `lstat`/`samestat` identity. A whole-tree `out` that reaches `source` through a case alias or bind mount is now rejected. A permission error from `lstat` on `out` or one of its ancestors now fails the step where a path comparison would not. The new behaviour is stricter and safe. Only bundle tests (`test_bundle_case_containment.py`) pin it, and `TestOutInsideSource` covers plain paths only. | File: src/tools/backup/capabilities/tar_archive.py:298 | Task: Phase 0
[BLAKE] ⚪ The CHANGELOG entry was written under `[Unreleased]` and then moved into `[0.17.0] - 2026-11-04` by the `v0.17.0` bump. The cycle-2 fixes came after that release: case-alias outputs inside a selected item are now rejected, and output identity errors are reported as failures. `[Unreleased]` is empty, so these user-visible fixes have no entry. The 0.17.0 line claims inside-item outputs always fail, but the shipped 0.17.0 code missed case aliases on case-insensitive filesystems. | File: CHANGELOG.md:8 | Task: Phase 1

The PRD behaviours are all implemented in `src/tools/backup/capabilities/tar_archive.py`:
- **Order in `run` and `_plan_source`:** both normalize `items` before `_reject_out_inside_source`, inside the same `except (ValueError, OSError)`. Invalid `items` therefore keep their own message and win over containment (`tar_archive.py:159`, `tar_archive.py:354`).
- **`out` equal to `source`:** it still fails with the source message in both modes.
- **Whole-tree runs:** with `items` omitted or `null`, any `out` under `source` still fails with the source message.
- **Bundles:** an `out` equal to or under `source / item` fails with the exact message the PRD asks for. Symlinked items get no parent check, which matches the Risks section.
- **Plan, run and dry-run:** the plan row carries `containment.message`, and the Runner turns plan `fail` rows into run results. All three modes therefore report the same reason.
- **Second run:** a bundle archives only its selected members, so an existing `out` under `source` is never a member.

Tests cover every scenario in the PRD's Test Strategy, in both engines where the file already parametrizes them. They are in `test_bundle_items.py` (`TestBundleOutContainment`), `test_plan_validation.py` (all three modes, capability and runner) and `test_bundle_case_containment.py`. `test_out_inside_source_fails_no_archive` and `test_stamped_out_inside_source_fails` are still present in `test_tar_archive.py`. The docs (`docs/source/tools/backup.rst:157`) and the CHANGELOG line both contain "selected item". The docs paragraph is longer than the one sentence the PRD asked for, but it is accurate. The supplied gate evidence says the suite, ruff and mypy pass.

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

### Openai

[BLAKE] 🟡 B1/B5: `_same_path` equates distinct hard links. With `items: [config]`, an existing `out` outside every item that hard-links `config` incorrectly fails containment in all modes. Atomic replacement would preserve `config`; compare directory entries rather than inode identity. | File: src/tools/backup/capabilities/tar_archive.py:276 | Task: general
[BLAKE] ⚪ B15: The required Fixed entry appears under `[0.17.0]`; the specification requires it under `[Unreleased]`, which is empty. | File: CHANGELOG.md:28 | Task: general

B1: fail
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
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Both provider outputs follow.

### Anthropic

Both prior-cycle findings are resolved:
- **Double normalization:** `run` and `_plan_source` now normalize items once and pass `selected` on to `_run_validated` and `_plan_items`.
- **Case-insensitive alias:** `_same_path` now compares filesystem identity (lstat plus samestat), and `test_case_alias_of_selected_directory_rejects_output_without_changes` covers it in every mode and with both engines.

The rework introduced no correctness regression. `_select_items`, `_plan_items` and the new containment handler all return OSError as `str(exc)`, so run and plan still give the same failure messages.

FIX:
- [BOB] 🟡 The source checks also moved from lexical comparison to filesystem identity: `out` equal to `source`, and the whole-tree ancestor check. Now a whole-tree `out` under a case alias of `source` is refused, where before it was allowed and the archive re-archived itself on every run. No test covers this new behavior; every `_case_alias` test uses a selected item. | File: src/tools/backup/capabilities/tar_archive.py:298 | Task: 2 — fix: in tests/tools/backup/test_bundle_case_containment.py, add a test that uses `_case_alias(source)`. It must check that a whole-tree `out` under the alias, and a bundle `out` equal to the alias, both fail with the source message, unchanged files, in every mode and with both engines.
- [BOB] ⚪ The `selected: list[Path] | None = None` default is never used, because both callers (`run` and `_plan_source`) always pass `selected`. | File: src/tools/backup/capabilities/tar_archive.py:282 | Task: 2 — fix: remove the default so `selected` is required.
- [BOB] ⚪ The new test file repeats cases that do not add coverage. The `error` values ("output identity permission denied", "archive metadata access denied") take the same `Path.lstat` patch path. The `selected` values `Config` and `Profiles` take the same swapcase path. `test_invalid_items_take_precedence_over_output_containment` repeats `test_invalid_items_win_over_containment_in_every_mode` (test_plan_validation.py) and `test_invalid_items_win_over_containment` (test_bundle_items.py). | File: tests/tools/backup/test_bundle_case_containment.py:49 | Task: 2 — fix: keep one value for each of those parametrizations (lines 49, 78, 102) and delete the duplicate invalid-items test at line 169.
- [BOB] ⚪ The docs give the wrong reason for refusing an `out` equal to a selected item. "because the archive would re-archive itself" does not fit that case, because writing `out` there would overwrite the selected item. The PRD also asked for one sentence; this paragraph has seven. | File: docs/source/tools/backup.rst:159 | Task: 1 — fix: change the reason to "because writing it would overwrite or re-archive a selected item" and cut the sentences that only restate whole-tree behavior.

VERIFY:
- (none)

KNOWN:
- (none)

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

### Openai

[BOB] ✅ No issues found

FIX:
- (none)

VERIFY:
- (none)

KNOWN:
- (none)

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
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Verdict: 7 findings
Tests: 6660 passed, 0 failed, 16 skipped (suite run this cycle)
