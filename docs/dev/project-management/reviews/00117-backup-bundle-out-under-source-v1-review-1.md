---
prd: docs/dev/project-management/prds/wip/00117-backup-bundle-out-under-source-v1.md
review: 1
date: 2026-11-05
head_sha: 67b14f9891666835a365f7fd20496bf37f5256ab
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
dispatch_rows:
  bob: f10b8469
---

# Review: 00117-backup-bundle-out-under-source-v1

Diff range: `5ae5c53e49ad95d94562b60df99aa272e0772cc5..67b14f9891666835a365f7fd20496bf37f5256ab`

codex_rung_guard: not fired
provider_review_guard: satisfied
autocodex_alice_openai_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c1-alice-openai.txt.receipt.json
autocodex_blake_openai_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c1-blake-openai.txt.receipt.json
autocodex_bob_openai_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00117-c1-bob-openai.txt.receipt.json

The model-provider guard supersedes the legacy implementor guard. Eve did not run.
All three required reviewers used fresh external OpenAI gpt-6.1-sol sessions through the host helper.
High effort was requested by the host contract; receipts and raw metadata retain the helper's observed fields unchanged.
The implementation audit verified Anthropic Claude Sonnet 5.5 contributors, including test writers and coordinator edits.
Carl: not invoked; this PRD has no frontend change.

## Review Summary

Reviewed one completed task against the complete PRD. No prior review findings were supplied.
Blake received the PRD and gate evidence only. Alice received implementation context; Bob received the complete inlined context, diff, consensus rubric, doubt rubric and de-slop appendix.
The work range is preserved from the original work start. Unrelated subsequent sysup/release changes do not change this PRD's provenance.
Staging initially refused the untracked local app icon; the file was preserved and `.herdr/` was excluded locally.
The initial staging dispatch row dc306370 was closed without dispatch, then staging was rerun.
The automated fail-first replay reported a mise error. Alice independently inspected/replayed tests; her raw findings are retained below.
No mechanical tautology findings were emitted. No prior-cycle verification queue exists.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/3] | 🟡 | Items are normalized twice in both run and plan. Normalize once and pass the selected paths to containment and selection. | src/tools/backup/capabilities/tar_archive.py:285 | 1 | ALICE, BOB |
| R2 | [1/3] | 🟠 | The new item comparison can allow output inside a selected directory on case-insensitive filesystems: items ["Config"] and out "<source>/config/archive.tar.gz" compare unequal lexically but address the same directory. Previously the whole-source guard rejected this configuration. Compare filesystem identity for existing ancestors while preserving final-symlink semantics; add coverage for both engines and every mode. | src/tools/backup/capabilities/tar_archive.py:299 | 1 | BOB |
| R3 | [1/3] | 🟡 | Item normalization now runs outside the plan’s OSError handler: simulated unreadable item parents returned a failed PlanEntry before, but now raise PermissionError. Preserve error conversion and add coverage. | src/tools/backup/capabilities/tar_archive.py:285 | 1 | ALICE |
| R4 | [1/3] | 🟡 | Replay confirms 32 added whole-tree/source-equality cases pass against pre-change code, violating the supplied fail-first rule. Reuse existing invariant coverage and make new cases exercise changed precedence. | tests/tools/backup/test_plan_validation.py:333 | 1 | ALICE |
| R5 | [1/3] | ⚪ | Required Fixed entry appears under `0.17.0`; `[Unreleased]` is empty, contrary to Phase 1. | CHANGELOG.md:28 | general | BLAKE |
| R6 | [1/3] | ⚪ | `_walk_tree` remains 70 lines according to the supplied mechanical facts, exceeding R12's 50-line limit. This function is unchanged; splitting it belongs outside this containment fix. | src/tools/backup/capabilities/tar_archive.py:427 | general | BOB |
| R7 | [1/3] | ⚪ | The supplied full-suite gate has three failures attributed to host author identity and configured roots. These concern unrelated tools and do not establish a backup regression. | N/A | general | BOB |

## Decision Gate

- R1: fix. Two reviewers identify redundant normalization; normalize once while preserving validation and error conversion.
- R2: fix. Confirmed on this case-insensitive APFS checkout: create Config, choose items Config, then use output config/archive.tar.gz. The alternate parent exists and the containment guard returns None. The fix is bounded validation inside a private helper; it changes no public API or schema.
- R3: discard under the mandatory single-voice Medium/Low rule. Retain the reported OSError regression as review evidence; error conversion must remain intact when normalization is changed.
- R4: discard under the mandatory single-voice rule. Existing whole-tree/source-equality invariants intentionally remain true before and after this change; passing replay alone does not make such regression coverage tautological.
- R5: discard. Release 0.17.0 correctly moved the previously Unreleased entry into its release section; restoring a duplicate Unreleased entry would misstate release history.
- R6: discard. The function is unchanged and outside this bounded containment fix; single voice.
- R7: discard as a PRD finding. Preserve the actual three unrelated suite failures in durable verification evidence and a deferred record.

### Verification evidence

The coordinator reproduced R2 in a temporary directory without writing an archive: case_insensitive=true; out_parent retains config; guard_result=None. The temporary directory was cleaned.
Backup ruff passed. Backup mypy passed for 11 files. Blake independently ran test_bundle_items.py: 106 passed.
The full suite ran twice with the same 6567 passed, 3 failed, 16 skipped and 1 xfailed result.
The required structured gate was recorded by autopilot verify, not by a manual state write.
Full output: `docs/dev/project-management/autopilot/reports/00117-c1-full-suite.log`.
Verification record: `docs/dev/project-management/autopilot/reports/00117-c1-verification.json`.
The two klyreon author failures match the inherited GIT_AUTHOR_NAME overriding per-command user.name; the postup test removes only its environment roots and still reads local configured roots.

## Alice

Provider: OpenAI

[ALICE] 🟡 Item normalization now runs outside the plan’s OSError handler: simulated unreadable item parents returned a failed PlanEntry before, but now raise PermissionError. Preserve error conversion and add coverage. | File: src/tools/backup/capabilities/tar_archive.py:285 | Task: 1
[ALICE] 🟡 Items are normalized twice in both run and plan. Normalize once and pass the selected paths to containment and selection. | File: src/tools/backup/capabilities/tar_archive.py:285 | Task: 1
[ALICE] 🟡 Replay confirms 32 added whole-tree/source-equality cases pass against pre-change code, violating the supplied fail-first rule. Reuse existing invariant coverage and make new cases exercise changed precedence. | File: tests/tools/backup/test_plan_validation.py:333 | Task: 1

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
R12: pass
R13: pass

## Blake

Provider: OpenAI

[BLAKE] ⚪ Required Fixed entry appears under `0.17.0`; `[Unreleased]` is empty, contrary to Phase 1. | File: CHANGELOG.md:28 | Task: general

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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Provider: OpenAI

FIX:
[BOB] 🟠 The new item comparison can allow output inside a selected directory on case-insensitive filesystems: items ["Config"] and out "<source>/config/archive.tar.gz" compare unequal lexically but address the same directory. Previously the whole-source guard rejected this configuration. Compare filesystem identity for existing ancestors while preserving final-symlink semantics; add coverage for both engines and every mode. | File: src/tools/backup/capabilities/tar_archive.py:299 | Task: 1
[BOB] 🟡 Item normalization now happens inside containment and again in the existing run/plan selection paths. Normalize once per path and pass the normalized selection into containment, as the PRD specifies; retain explicit validation errors. | File: src/tools/backup/capabilities/tar_archive.py:285 | Task: 1

VERIFY:
- (none)

KNOWN:
[BOB] ⚪ `_walk_tree` remains 70 lines according to the supplied mechanical facts, exceeding R12's 50-line limit. This function is unchanged; splitting it belongs outside this containment fix. | File: src/tools/backup/capabilities/tar_archive.py:427 | Task: general
[BOB] ⚪ The supplied full-suite gate has three failures attributed to host author identity and configured roots. These concern unrelated tools and do not establish a backup regression. | File: N/A | Task: general

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
R12: fail
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Verdict: 7 findings
Tests: 6567 passed, 3 failed, 16 skipped (suite run this cycle)
