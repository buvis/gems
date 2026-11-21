---
prd: docs/dev/project-management/prds/wip/00139-shared-config-typos-invisible-v1.md
review: 1
date: 2026-11-14
head_sha: 9891ecdea3adca7af0672d53eb85175256a31eb3
codex_thread_id: 01a1d7bb-a3a5-7570-8617-14016abaf1e4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: b2936113
  carl: 479f4ca5
---

# Review: 00139-shared-config-typos-invisible-v1 (cycle 1)

Diff range: `eca0df13e18cd1c6ae55a79c19af57eb21233618..9891ecdea3adca7af0672d53eb85175256a31eb3`

codex_rung_guard: not fired

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00139-shared-config-typos-invisible-v1.md
Scope: full review of the PRD's whole work range.

### Agent Status

- Alice: ✅ Available (consensus lens, Claude subagent, `consensus_engine: legacy`)
- Blake: ✅ Available (blind lens, PRD-only; ran his own probe)
- Bob: ✅ Available (doubt lens, codex, fresh thread `01a1d7bb-a3a5-7570-8617-14016abaf1e4`; D1-D5 emitted)
- Carl: ✅ Available (gemini via copilot backend)

### Cycle notes

- Engram context pack: failed (`engram pack exit 1: not inside a registered repo`). Reviewers ran with the `(no pack available this cycle)` sentinel. Degraded, not invalid.
- Fail-first replay: skipped — the replay runner produced no results (`No module named pytest` in the base worktree's venv). Alice judged test-pinning by reading instead, and says so in her ⚪ row.
- Tautological-test check ran over 12 test functions in 2 changed test files and emitted zero `[MECH]` lines.
- No cycle-0 verification-check queue exists, so nothing was carried forward. Bob's VERIFY bucket is empty, so this cycle writes no queue file.
- `review-stage`'s own gate run printed no PASS/FAIL/SKIP/EXIT summary line (`pytest -q` alone does not), so the staged context carried `counts unavailable`. The gate was re-run once through `autopilot verify` with a wrapper that emits the summary line; the `Tests:` line below comes from that run.
- `consolidate_findings.py` merged three row pairs on suffix-stripped citations. Two merges are correct (same defect, adjacent lines). The third swallowed a **distinct** Blake 🟠 — his "the check does not know any other tool's settings fields" finding at `resolver.py:207` was folded into R1 at `resolver.py:204`. It is restored below as its own row, **R11**, so it carries its own disposition instead of disappearing into R1.
- R4 (Alice) and R7 (Carl) are one defect in two wordings (no test pins the real entry-point wiring). The consolidator kept them apart because their line refs differ. The decision gate treats R4 as the surviving row with two finders and retires R7 as a duplicate.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | Valid global fields `debug` and `log_level` produce the unknown-key warning when the caller resolves plain `GlobalSettings`. `resolve()` sets `known_keys` to None whenever `tool_name` is None (the default `BUVIS_` prefix), and the shared-file branch then treats every key that isn't a tool name as unknown. The spec requires no warning for a global field. Probes by two reviewers confirmed warnings for `debug` and `log_level` under `GlobalSettings`. `resolver.resolve(GlobalSettings)` is a documented public API path (the class docstring's own examples), so the design's "not exercised by any real tool CLI" is true of the shipped CLIs but not of the public API. | src/lib/buvis/pybase/configuration/resolver.py:204 | 3 | BLAKE, BOB, CARL |
| R2 | [3/4] | 🟡 | `ConfigResolver._load_yaml` grows from about 43 to 60 lines, over the 50-line limit (see the mechanical facts block). The new shared-file check also sits 5 levels deep (for, try, if, for, if). Extract the `config.yaml`/`buvis.yaml` branch into a helper such as `_warn_unknown_shared_keys(layer, path, known_keys)` and hoist `known_tool_names()` out of the per-key loop. Behavior stays the same. | src/lib/buvis/pybase/configuration/resolver.py:175 | 3 | ALICE, BOB, CARL |
| R3 | [2/4] | 🟡 | `test_registry.py` leaves a monkeypatched value in the process-wide `lru_cache`. `test_result_is_cached_until_cleared` ends with the cache holding `{"delta"}`, and the other two tests end holding their fakes. Nothing clears the cache after them. Later tests in the same pytest process that resolve against `config.yaml`/`buvis.yaml` then see a bogus registry and emit spurious warnings. The design's Risks section names this leak. Add an autouse fixture in this module that calls `known_tool_names.cache_clear()` on teardown as well as on setup. | tests/lib/pybase/configuration/test_registry.py:13 | 2 | ALICE, BOB |
| R4 | [2/4] | 🟡 | No test asserts the real entry-point wiring. The design's "Integration (real entry points, no monkeypatching)" bullet is not implemented. A missing or misspelled line among the 18 registrations would go unnoticed, and this PRD names that as its main risk. Add a test that `known_tool_names()` matches the declared tool set, so registry drift fails in CI. | tests/lib/pybase/configuration/test_registry.py:1 | 1 | ALICE, CARL |
| R5 | [1/4] | 🟡 | No test covers either gap. There is no test that resolves `GlobalSettings` against a shared file with `debug`, and none that resolves one tool against a shared file carrying another tool's top-level field. The new tests only resolve `BraidSettings` against its own fields and the `sysup`/`adapters` namespace sections. | tests/lib/pybase/configuration/test_tool_config_keys.py:68 | 3 | BLAKE |
| R6 | [1/4] | 🟡 | `known_tool_names()` is cached for the process lifetime and reads installed distribution metadata. A stale editable install, or a tool whose entry point is not registered, turns a valid `<tool>:` section into a warning. The code docstring and the docs both admit this. Nothing guards the entry-point list in `pyproject.toml` against the set of tool settings classes, so a new tool can silently go unregistered. | src/lib/buvis/pybase/configuration/registry.py:23 | 1 | BLAKE |
| R7 | [1/4] | 🟡 | TestKnownToolNames monkeypatches entry_points in all tests; add an integration test asserting known_tool_names discovers real tools registered in pyproject.toml | tests/lib/pybase/configuration/test_registry.py:12 | 2 | CARL |
| R8 | [1/4] | ⚪ | `tools/lib/scaffold.py` and `tools/lib/check_tool_wiring.py` do not enforce or generate the new `buvis.config_settings` entry. The design records this as an accepted follow-on, so any newly scaffolded tool will emit noisy warnings for its own `<tool>:` section until someone adds the line by hand. Consider a follow-up PRD or triage stub. | tools/lib/scaffold.py | general | ALICE |
| R9 | [1/4] | ⚪ | `test_shared_config_own_valid_fields_produce_no_warning` and the added `caplog` assertion in `test_shared_config_keeps_other_tool_namespaces` also pass against the pre-change code, so they only guard against false positives and do not pin the fix. `test_shared_config_warns_on_resolving_tools_own_typo` does pin it. This is acceptable as design-mandated guard tests. The fail-first replay did not run, so this is judged by reading the tests, not by replay. | tests/lib/pybase/configuration/test_tool_config_keys.py:77 | 3 | ALICE |
| R10 | [1/4] | ⚪ | The spec's evidence case is met. `srouces:` in a file named `config.yaml` or `buvis.yaml` warns, naming the file and key, and does not fail. The same content in `custom.yaml` still raises `ConfigurationError`. The library imports no tool code, because the registry reads only `EntryPoint.name`. A CHANGELOG entry is present, under the Unreleased `Fixed` section, and `docs/source/configuration.rst` is updated. | CHANGELOG.md:31 | general | BLAKE |
| R11 | [1/4] | 🟠 | The check only knows the resolving tool's own fields and the registered tool names. It does not know "any tool's settings field", which is what Success Metric 1 says. A top-level `sources:` in `config.yaml` is a valid braid field; running sysup against that file warns `unknown configuration key 'sources'`, confirmed by probe. The registry stores only entry-point names, with no per-tool key sets. | src/lib/buvis/pybase/configuration/resolver.py:207 | 3 | BLAKE |

## Alice

Implementation-aware consensus lens. Rows R2, R3, R4, R8, R9 above.

Checks Alice ran:
- All 18 entry-point names resolve in the uv environment and match `src/tools/*/settings.py`.
- `tests/lib/pybase/configuration/test_registry.py` and `test_tool_config_keys.py` give 32 passed.
- Every tool settings class uses `extra="forbid"`, so the `known_keys is None` branch cannot cause false-positive warnings for real tools.
- The explicit/custom-file branch (`elif known_keys is not None`) is unchanged.
- The docs paragraph and the CHANGELOG entry match the shipped behavior.

Per-rule verdicts:

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
R13: pass

## Blake

Blind lens, PRD only — no diff, no file list, no review history. He located the code himself and ran one probe resolving `GlobalSettings`, `SysupSettings` and `BraidSettings` against a shared `config.yaml` holding `debug`, `log_level`, `sources`, `sysup:` and the typo `srouces`. Rows R1, R11, R5, R6, R10 above.

Per-rule verdicts:

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
B15: pass
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop (codex, static-only sandbox, inlined prompt). Rows R1, R2, R3 above.

FIX:
- Valid global fields produce false warnings when `known_keys=None`, including `resolve(GlobalSettings)` with `debug: true`. Supply the resolving class's fields for shared-file validation while preserving permissive custom-file behavior; add regression coverage. — src/lib/buvis/pybase/configuration/resolver.py:207
- Registry tests leave mocked names cached after monkeypatch teardown; the final test leaves `{"delta"}` available to subsequent callers. Add a function-scoped fixture that clears the cache before and after each registry test. — tests/lib/pybase/configuration/test_registry.py:37
- `_load_yaml` now spans 60 lines, exceeding the 50-line limit. Extract the per-layer key validation into a focused helper, preserving warning and rejection behavior. — src/lib/buvis/pybase/configuration/resolver.py:175

VERIFY:
- (none)

KNOWN:
- (none)

Per-rule verdicts:

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

Doubt rubric verdicts:

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via the copilot backend. His raw output opens with a tool-use trace (two "too large, not read" notices, then chunked reads of the context and diff) before the issue lines; he read both staged inputs in slices and ran his own probes. Rows R1, R2, R7 above, plus one ⚪ he alone raised (the `known_keys is not None` check inside the per-key loop is loop-invariant), which R2's extraction subsumes.

Per-rule verdicts:

R1: pass
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

Verdict: 11 findings
Tests: 7701 passed, 0 failed, 16 skipped (suite run this cycle)

Gate caveat, stated plainly: the suite's process exit was 1, not 0. Ten tests in
`tests/tools/dot/test_pull_divergence_two_hosts.py` error out on a `git commit`
returning 128 under this sandbox's gpgsign configuration. That is the same
environment-only failure `state.work_verification_note` and the two prior PRDs in
this batch recorded, it is unrelated to this PRD's diff, and it is not counted as
a failure above because no test in the suite failed.
