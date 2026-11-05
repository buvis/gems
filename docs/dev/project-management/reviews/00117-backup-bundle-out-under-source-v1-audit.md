# Decision Audit Log: 00117-backup-bundle-out-under-source-v1

PRD: `00117-backup-bundle-out-under-source-v1.md`
Started: 2026-11-05T11:42:15Z
Completed: 2026-11-05T11:42:15Z
Autonomous: 23  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: PRD 00117 completion lacks provider-independent review evidence

**Choice**: Restore verified implementation provenance and resume fresh cycle-1 review

**Rationale**: Original Claude Sonnet 5.5 implementation records verified; preserve prior review and pause snapshot, clear obsolete convergence, retain tasks and cap. Interactive recovery and standing authorization permit this reversible correction.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Items are normalized twice in both run and plan. Normalize once and pass the selected paths to containment and selection.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: The new item comparison can allow output inside a selected directory on case-insensitive filesystems: items ["Config"] and out "<source>/config/archive.tar.gz" compare unequal lexically but address the same directory. Previously the whole-source guard rejected this configuration. Compare filesystem identity for existing ancestors while preserving final-symlink semantics; add coverage for both engines and every mode.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Items are normalized twice in both run and plan. Normalize once and pass the selected paths to containment and selection.

**Choice**: fix

**Rationale**: Two independent voices identify redundant normalization; bounded private-helper refactor with error conversion preserved.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: The new item comparison can allow output inside a selected directory on case-insensitive filesystems: items ["Config"] and out "<source>/config/archive.tar.gz" compare unequal lexically but address the same directory. Previously the whole-source guard rejected this configuration. Compare filesystem identity for existing ancestors while preserving final-symlink semantics; add coverage for both engines and every mode.

**Choice**: fix

**Rationale**: Coordinator reproduced case-insensitive Config/config containment escape on APFS. Additive validation and tests within the private containment helper; no public API/schema change.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Item normalization now runs outside the plan’s OSError handler: simulated unreadable item parents returned a failed PlanEntry before, but now raise PermissionError. Preserve error conversion and add coverage.

**Choice**: discard

**Rationale**: Mandatory single-voice Medium discard; reported OSError conversion remains evidence for the normalization fix.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Replay confirms 32 added whole-tree/source-equality cases pass against pre-change code, violating the supplied fail-first rule. Reuse existing invariant coverage and make new cases exercise changed precedence.

**Choice**: discard

**Rationale**: Single voice; tests pin unchanged safety invariants, for which passing against base is expected.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Required Fixed entry appears under `0.17.0`; `[Unreleased]` is empty, contrary to Phase 1.

**Choice**: discard

**Rationale**: The intervening 0.17.0 release legitimately moved the Unreleased changelog entry.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: `_walk_tree` remains 70 lines according to the supplied mechanical facts, exceeding R12's 50-line limit. This function is unchanged; splitting it belongs outside this containment fix.

**Choice**: discard

**Rationale**: Single voice; unchanged function outside this bounded fix.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: The supplied full-suite gate has three failures attributed to host author identity and configured roots. These concern unrelated tools and do not establish a backup regression.

**Choice**: discard

**Rationale**: Single voice; full-suite host-dependent failures concern unrelated tools, retained in verification and deferred evidence.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Pat delta review relabels redundant is_symlink guard as MEDIUM

**Choice**: retain for completion review

**Rationale**: No correctness defect identified; the same response also reports it as LOW. Per supplied severity contract this is behavior-preserving simplification, so no additional repair. Confirmed identity OSError MEDIUM was fixed and 90 tests pass.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Whole-tree containment and bundle source-equality now compare by filesystem identity (lines 298-299). On APFS, a case alias is now rejected: source `<tmp>/Src` with out `<tmp>/src/x.tar.gz` (old lexical guard allowed it). An out equal to a source alias now gets the source message. No test covers either branch. If both lines go back to lexical comparison, the suite still passes, because the permission test then raises in the item loop instead. Add case-alias cases for whole-tree and for bundle `out == source`, skipped like `_case_alias`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Inode equality rejects valid hard-linked output names outside the selected items. For items ["a"], an external out hard-linked to source/a fails, although atomic replacement preserves a. Distinguish path aliases from distinct hard links and add coverage across both engines and all modes.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: The new default `selected: list[Path] | None = None` is never used, because both callers (lines 161, 362) pass the argument. Make it a required parameter.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: `test_invalid_items_take_precedence_over_output_containment` repeats `test_invalid_items_win_over_containment` (tests/tools/backup/test_bundle_items.py:471) and `test_invalid_items_win_over_containment_in_every_mode` (tests/tools/backup/test_plan_validation.py:375). It uses the same messages, engines and modes. Invalid items can never reach the item branch, so putting `out` inside `Config` tests no new path. Delete it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Some parametrizations repeat one code path. Both `error` values inject the same `lstat(out)` failure, and the `selected` value "Profiles" exercises the same path as "Config" (:78, :102). Drop the duplicates.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Whole-tree containment and bundle source-equality now compare by filesystem identity (lines 298-299). On APFS, a case alias is now rejected: source `<tmp>/Src` with out `<tmp>/src/x.tar.gz` (old lexical guard allowed it). An out equal to a source alias now gets the source message. No test covers either branch. If both lines go back to lexical comparison, the suite still passes, because the permission test then raises in the item loop instead. Add case-alias cases for whole-tree and for bundle `out == source`, skipped like `_case_alias`.

**Choice**: tail sweep queued

**Rationale**: Shared bounded finding; normal work pipeline in fresh session, no review cycle increment.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Inode equality rejects valid hard-linked output names outside the selected items. For items ["a"], an external out hard-linked to source/a fails, although atomic replacement preserves a. Distinguish path aliases from distinct hard links and add coverage across both engines and all modes.

**Choice**: tail sweep queued

**Rationale**: Shared bounded finding; normal work pipeline in fresh session, no review cycle increment.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: The new default `selected: list[Path] | None = None` is never used, because both callers (lines 161, 362) pass the argument. Make it a required parameter.

**Choice**: tail sweep queued

**Rationale**: Shared bounded finding; normal work pipeline in fresh session, no review cycle increment.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: `test_invalid_items_take_precedence_over_output_containment` repeats `test_invalid_items_win_over_containment` (tests/tools/backup/test_bundle_items.py:471) and `test_invalid_items_win_over_containment_in_every_mode` (tests/tools/backup/test_plan_validation.py:375). It uses the same messages, engines and modes. Invalid items can never reach the item branch, so putting `out` inside `Config` tests no new path. Delete it.

**Choice**: tail sweep queued

**Rationale**: Shared bounded finding; normal work pipeline in fresh session, no review cycle increment.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: Some parametrizations repeat one code path. Both `error` values inject the same `lstat(out)` failure, and the `selected` value "Profiles" exercises the same path as "Config" (:78, :102). Drop the duplicates.

**Choice**: tail sweep queued

**Rationale**: Shared bounded finding; normal work pipeline in fresh session, no review cycle increment.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: The CHANGELOG entry was written under `[Unreleased]` and then moved into `[0.17.0] - 2026-11-04` by the `v0.17.0` bump. The cycle-2 fixes came after that release: case-alias outputs inside a selected item are now rejected, and output identity errors are reported as failures. `[Unreleased]` is empty, so these user-visible fixes have no entry. The 0.17.0 line claims inside-item outputs always fail, but the shipped 0.17.0 code missed case aliases on case-insensitive filesystems.

**Choice**: discard

**Rationale**: single-voice Medium/Low mandatory discard; retained in settled ledger.

### [autonomous] 2026-11-05T11:42:15Z

**Decision**: The docs give the wrong reason for refusing an `out` equal to a selected item. "because the archive would re-archive itself" does not fit that case, because writing `out` there would overwrite the selected item. The PRD also asked for one sentence; this paragraph has seven.

**Choice**: discard

**Rationale**: single-voice Medium/Low mandatory discard; retained in settled ledger.

### [deferred] 2026-11-05T11:42:15Z

**Decision**: Full-suite host-dependent failures: klyreon author identity (two tests) and postup local roots (one test)

**Choice**: defer unrelated test isolation fixes

**Rationale**: Both full-suite runs: 6567 passed, 3 failed, 16 skipped, 1 xfailed. Backup checks pass. See reports/00117-c1-full-suite.log; no unrelated source changes made.
