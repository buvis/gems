---
prd: docs/dev/project-management/prds/wip/00139-shared-config-typos-invisible-v1.md
review: 2
date: 2026-11-14
head_sha: 102c6198359593ac6d699408b9e168a19319af31
codex_thread_id: 01a1d7bb-a3a5-7570-8617-14016abaf1e4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 2ac2340e
  carl: 1f3ed8ec
---

# Review: 00139-shared-config-typos-invisible-v1 (cycle 2)

Diff range: `9891ecdea3adca7af0672d53eb85175256a31eb3..102c6198359593ac6d699408b9e168a19319af31`

codex_rung_guard: not fired

## Review Summary

Reviewed: 6 completed tasks (4 original + the cycle-1 rework tasks 5 and 6)
PRDs checked: 00139-shared-config-typos-invisible-v1.md
Scope: incremental review of the rework commits since cycle 1 (`ea0c84c4` resolver.py fix, `0c5a4654` test_registry.py fix).

### Agent Status

- Alice: ✅ Available (consensus lens, Claude subagent, `consensus_engine: legacy`)
- Blake: ✅ Available (blind lens, PRD-only; ran his own probe)
- Bob: ✅ Available (doubt lens, codex, resumed thread `01a1d7bb-a3a5-7570-8617-14016abaf1e4`; D1-D5 emitted)
- Carl: ✅ Available (gemini via copilot backend)

### Cycle notes

- Engram context pack: failed (`engram pack exit 1: not inside a registered repo`). Reviewers ran with the `(no pack available this cycle)` sentinel. Degraded, not invalid.
- Fail-first replay: skipped — the replay runner produced no results (`ModuleNotFoundError: No module named 'inflection'` in the base worktree's venv). Alice judged test-pinning by reading instead, and says so.
- Tautological-test check ran over 4 test functions in 1 changed test file and emitted zero `[MECH]` lines.
- Cycle 1 wrote no verification-check queue (Bob's VERIFY bucket was empty), so nothing is carried forward. Bob's cycle-2 VERIFY bucket is also empty, so this cycle writes no queue file either.
- `consolidate_findings.py` merged Alice's and Carl's rows on suffix-stripped citations (`test_tool_config_keys.py:67 ~ :68`) — correct, one defect in two wordings.
- **R4 (Bob) is the same defect as R1** (the mandated `GlobalSettings` regression tests were never delivered). The consolidator kept them apart because Bob cited `resolver.py:302` while Alice and Carl cited the test file. The decision gate treats R1 as the surviving row with **three** finders (ALICE, CARL, BOB) and retires R4 as a duplicate.
- Blake's 🟠 re-raise of the "other tools' valid top-level keys warn" gap was auto-dismissed by the ledger (settled deferral from cycle 1). His 🟡 R3 is the same deviation in narrower words and survives in the table as a single voice; it is treated as the same settled deferral at the gate.
- The 10 failing tests in the gate run are all collection ERRORs in `tests/tools/dot/test_pull_divergence_two_hosts.py`, caused by this host's `commit.gpgsign=true` needing interactive 1Password approval. Pre-existing, unrelated to this PRD, already recorded as a deferred decision. The configuration module's own suite is green (67 passed across `test_registry.py`, `test_tool_config_keys.py`, `test_resolver.py`).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | Prior R1 is fixed in code but not pinned by any test. The task required regression tests: (a) `resolve(GlobalSettings)` on a `config.yaml` with `debug`/`log_level` emits no warning, and (b) `GlobalSettings` against `srouces` still warns. The incremental diff does not touch `tests/lib/pybase/configuration/test_tool_config_keys.py`. Its only `GlobalSettings` use is `LenientSettings` (line 102). Every shared-file test there resolves `BraidSettings`, so reverting the `_own_fields` change would leave the whole suite green. Probes confirm the fix works (no warning for `debug`/`log_level`, a warning for `srouces`), but nothing guards it. | tests/lib/pybase/configuration/test_tool_config_keys.py:67 | 5 | ALICE, CARL, BOB |
| R2 | [2/4] | 🟡 | `resolve()` passes the own-field set to `_warn_unknown_shared_keys` through mutable instance state (`self._own_fields`) instead of the NEW keyword argument on `_load_yaml` that the task contract specified. `_load_yaml` now depends on `resolve()` having run first. A direct call, or one from a future caller, sees an empty set and warns on every own-field key. `known_keys = self._own_fields` also aliases that state. Simpler, behavior-preserving shape: compute `own_fields` as a local in `resolve()`, add `own_fields: set[str]` as a keyword parameter to `_load_yaml`, and drop `self._own_fields` and the line 201 initializer. | src/lib/buvis/pybase/configuration/resolver.py:201 | 5 | ALICE, BOB |
| R3 | [1/4] | 🟡 | Registry stores no key sets, so a typo in another tool's field or deferred key is only caught when that tool resolves. Other tools' fields are never consulted, which is a narrower check than the spec's "matches no tool's settings field". This is the same design deviation as the auto-dismissed row below. Phase 1 design choice is documented but is not the "tools register their key sets" option and does not satisfy the success metric. | src/lib/buvis/pybase/configuration/registry.py:23 | Phase 1 | BLAKE |
| R4 | [1/4] | 🟡 | Task 5's required `GlobalSettings` regression tests are absent; the earlier dismissal relied on their delivery. Add shared-file tests proving `debug`/`log_level` stay quiet and `srouces` still warns with file and key. | src/lib/buvis/pybase/configuration/resolver.py:302 | 5 | BOB |
| R5 | [1/4] | 🟡 | Registry discovery now runs even without shared files, adding an unnecessary distribution-metadata scan to explicit-file and empty-config resolutions. Move `known_tool_names()` into `_warn_unknown_shared_keys`, before its loop, and remove the `tool_names` argument. | src/lib/buvis/pybase/configuration/resolver.py:223 | 5 | BOB |
| R6 | [1/4] | ⚪ | The autouse fixture in `test_registry.py` already clears the cache before and after each test. The `known_tool_names.cache_clear()` calls at the start of `test_returns_exactly_the_registered_names` and the other pre-existing tests are now redundant. Only the mid-test clear in `test_result_is_cached_until_cleared` is load-bearing. | tests/lib/pybase/configuration/test_registry.py:30 | 6 | ALICE |
| R7 | [1/4] | ⚪ | The test gate reports 10 failures out of 7702 tests. I did not verify whether they relate to this change. The two targeted test files, `tests/lib/pybase/configuration/test_tool_config_keys.py` and `tests/lib/pybase/configuration/test_registry.py`, pass (33 tests). | N/A | general | BLAKE |
| R8 | [1/4] | ⚪ | The CHANGELOG `Fixed` entry exists (CHANGELOG.md:31). It claims "a key that is a valid field of the resolving tool, a global field, or another registered tool's namespace section" produces no warning. That is narrower than the PRD's "valid shared keys for any tool", but the entry is honest about it. The custom-named file rejection path is unchanged and the file name appears in the warning, as required. | CHANGELOG.md:31 | Phase 2 | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] 🟠 Valid top-level keys of other tools warn in shared files, contradicting "Valid shared keys for any tool produce no warning". The registry only holds tool names (entry-point names, no field sets). `_warn_unknown_shared_keys` accepts a key only if it is the resolving tool's own field or deferred key, or a tool name. I probed it by putting `instances: {}` (backup), `commands: {}` (sysup) and `srouces:` in `config.yaml`, then resolving BraidSettings. All three warned, so the sibling tools' valid keys produce the same noise as the typo. Docs say shared files are merged flat and top-level keys are for "every tool should see it". Success metric 1 says a key warns only if it matches no tool's field, no global field, and no declared deferred key. The Risks section expects the registry to hold key sets. The tests only cover `<tool>:` namespace sections (`sysup:`, `bim:`), never another tool's top-level field. | File: src/lib/buvis/pybase/configuration/resolver.py:100 — requirements ambiguity, deferred to batch end. The approved design doc settles it the other way: a shared file does not carry other tools' fields flat at the top level, it carries a `<tool>:` namespace section per tool (design lines 18-19 and 528). Closing the gap as Blake reads it needs per-tool field sets in the registry, which would make the library import tool code, against the AGENTS.md invariant the PRD itself restates.
- [BLAKE] ⚪ Name-only entry points mean a tool missing from `pyproject.toml` (or an uninstalled extra) makes its valid `<tool>:` section warn. The docstring and docs acknowledge this. The Risks section lists it, so it is acceptable. | File: src/lib/buvis/pybase/configuration/registry.py:30 — single-voice; the cache lifetime is a documented design choice, and the unregistered-tool half is what R4's entry-point drift test pins

## Alice

Implementation-aware consensus lens. Rows R1, R2, R6 above.

Prior findings status:

- R1 (GlobalSettings false positive): code resolved, probe confirmed. Regression tests not delivered — re-raised as this cycle's R1.
- R2 (`_load_yaml` over 50 lines and too deeply nested): resolved. The `_warn_unknown_shared_keys` helper is extracted and `known_tool_names()` is hoisted out of the loop. `_load_yaml` is 43 lines. Warning text, the `_split_directive` base-name handling and the custom-file raising branch are unchanged.
- R3 (cache leak in `test_registry.py`): resolved. The autouse fixture clears the cache on setup and teardown.
- R4 (no real entry-point wiring test): resolved. `TestRealEntryPointWiring` compares `known_tool_names()` to the `pyproject.toml` group with no monkeypatching. `parents[4]` resolves to the repo root, and it passes.
- R11 stays a settled deferral, not re-raised.

Checks Alice ran: `test_registry.py`, `test_tool_config_keys.py` and `test_resolver.py` give 67 passed. The fail-first replay did not run, so test pinning was judged by reading.

Per-rule verdicts: R1 fail, R2 fail, R3 pass, R4 pass, R6 pass, R7 pass, R8 pass, R9 pass, R10 pass, R11 pass, R12 pass, R13 pass.

## Blake

Blind lens (PRD-only, no diff). Rows R3, R7, R8 above, plus the two ledger-dismissed rows.

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens (codex, resumed thread). Rows R2, R4, R5 above.

FIX: the three rows above. VERIFY: none. KNOWN: none.

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

## Carl

Frontend & design specialist, generalist here (no UI surface in this PRD). Row R1 above (co-finder).

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

Verdict: 8 findings
Tests: 7702 passed, 10 failed, 16 skipped (suite run this cycle, exit 1, treated as failed)
