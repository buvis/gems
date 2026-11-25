---
prd: docs/dev/project-management/prds/wip/00137-yaml-auto-update-ignored-v1.md
review: 1
date: 2026-11-13
head_sha: 28a0580dc7c736e9654bf5a2b1abcdaaa8abc490
codex_thread_id: 01a1d6b7-edf2-7290-903b-1a89ba543ee3
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 4cf5bfc2
  carl: 143a229d
---

# Review: 00137-yaml-auto-update-ignored-v1

Diff range: `8d98134f09ee8b873d15eedbe27f16596bc7f88d..28a0580dc7c736e9654bf5a2b1abcdaaa8abc490`

codex_rung_guard: not fired

pack: failed (engram pack exit 1: worktree not registered with gita) - cycle degraded, not invalid.
replay: skipped (fail-first runner exit 1 under mise), so no mechanical replay evidence this cycle.

## Review Summary

### Agent Status

- alice: available (Claude subagent, consensus lens)
- blake: available (Claude subagent, blind/PRD-only lens)
- bob: available (codex, doubt rubric D1-D5 + de-slop)
- carl: available (copilot backend, model gemini-3.8-flash)
- eve: disabled (doubt_reviewer is codex and no task was implemented by codex, so the codex doubt-roster guard did not fire)

## Consolidated Findings

The one `[MECH]` tautological-shape line this cycle (`test_update_with_malformed_settings_exits_cleanly`) is carried as row R13; Carl raised it verbatim, so its finders are CARL + mech-check.

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [4/4] | 🟠 | `--config-dir` is not honoured by the new early resolution. `_extract_config_path` only parses `--config`, and `ConfigResolver().resolve(...)` never gets `config_dir`. With `--config-dir X`, where X holds `auto_update: false`, the update check still runs. Breaks the PRD contract of using the resolved `auto_update` and the `config.yaml` / `buvis-<tool>.yaml` success metric. Fix: extract `--config-dir` (and the `=` form) and pass it through. | src/lib/buvis/pybase/configuration/click_integration.py:132 | 1 | ALICE, BLAKE, BOB, CARL |
| R2 | [2/4] | 🟡 | `docs/source/configuration.rst:830-832` says the check honours "the fully resolved settings (CLI > ENV > YAML > defaults)". Inaccurate: the early resolution passes no CLI overrides and ignores `--config-dir`. | docs/source/configuration.rst:830 | 1 | ALICE, BLAKE |
| R3 | [2/4] | 🟡 | Test gaps: no test covers `--config-dir`, default-discovered `config.yaml` / `buvis-<tool>.yaml` (the PRD's own evidence case), the `--config=VALUE` form, the `--` sentinel, or `--help`/`--version` with YAML `auto_update: false`. | tests/lib/pybase/configuration/test_click_integration.py:1156 | 1 | ALICE, CARL |
| R4 | [1/4] | 🔴 | `_run_update_check_once` now takes `(ctx, args)`, but `tests/tools/sysup/conftest.py:20` still patches it with `lambda _ctx: None`; the patched `parse_args` calls it outside `contextlib.suppress`, so sysup/dot CLI tests raise `TypeError: <lambda>() takes 1 positional argument but 2 were given`. Independently reproduced by this gate: `pytest tests/tools/sysup tests/tools/dot` -> 86 failed, 1711 passed, 10 errors, 76 `TypeError` occurrences; `git show 8d98134f:tests/tools/sysup/conftest.py` proves the stub predates the diff, so the signature change is the cause and the "pre-existing redness" attribution in the build hand-off is wrong for this cause. Fix: `lambda _ctx, _args: None`. | tests/tools/sysup/conftest.py:20 | 1 | ALICE |
| R5 | [1/4] | 🟠 | Design deviates from the PRD: the check stays in the `parse_args` patch and re-resolves settings from raw argv instead of running in `wrapper` after `ConfigResolver.resolve`. The result is a second, partial resolution that ignores `--config-dir` and CLI overrides, with hand-rolled argv parsing that also scans subcommand args on a group. | src/lib/buvis/pybase/configuration/click_integration.py:147 | 1 | ALICE |
| R6 | [1/4] | 🟡 | Settings are now resolved twice per invocation, so resolver side effects (`_log_sources` info lines, loader warnings) fire twice. | src/lib/buvis/pybase/configuration/click_integration.py:167 | 1 | ALICE |
| R7 | [1/4] | 🟡 | The spec's ordering change (check after `ConfigResolver.resolve` in the wrapper) was not made; the second partial resolution can diverge from the wrapper's and loads config twice. | src/lib/buvis/pybase/configuration/click_integration.py:147 | 1 | BLAKE |
| R8 | [1/4] | 🟡 | `contextlib.suppress(Exception)` around the early check swallows every exception; on `--help`/`--version` a broken config silently skips the check with nothing reported. | src/lib/buvis/pybase/configuration/click_integration.py:162 | 1 | BLAKE |
| R9 | [1/4] | 🟡 | Test coverage thinner than the PRD's critical scenarios: no `--config-dir` test, no default-discovery test, no test that `updater.json` stays untouched. | tests/lib/pybase/configuration/test_click_integration.py:1157 | 1 | BLAKE |
| R10 | [1/4] | 🟡 | `_extract_config_path` returns the FIRST repeated `--config`, whereas Click uses the last value, so an enabled first file followed by a disabled one permits an unwanted update. | src/lib/buvis/pybase/configuration/click_integration.py:140 | 1 | BOB |
| R11 | [1/4] | 🟡 | The enabled-path test also passes against the original implementation because it only counts updater calls; assert the resolved `installer` value reaches the updater. | tests/lib/pybase/configuration/test_click_integration.py:1181 | 1 | BOB |
| R12 | [1/4] | 🟡 | The existing malformed-settings test's either-or assertion cannot pin the intended outcome (unchanged force-update test, outside this change). | tests/lib/pybase/configuration/test_click_integration.py:1066 | general | BOB |
| R13 | [1/4] | 🟡 | `test_update_with_malformed_settings_exits_cleanly` hedges with `or`: either outcome satisfies it. | tests/lib/pybase/configuration/test_click_integration.py:1066 | general | CARL, mech-check |
| R14 | [1/4] | ⚪ | Three of the five new tests are regression guards that should pass against the pre-change code; the replay was skipped so this is unconfirmed. Two tests pin the fix. | tests/lib/pybase/configuration/test_click_integration.py:1195 | 1 | ALICE |
| R15 | [1/4] | ⚪ | `test_click_integration.py` grows from 1153 to ~1250 lines, past the 800-line limit (already over before the diff). | tests/lib/pybase/configuration/test_click_integration.py:1156 | 1 | ALICE |
| R16 | [1/4] | ⚪ | The `[MECH]` note targets a test this diff did not touch: pre-existing, out of scope. | tests/lib/pybase/configuration/test_click_integration.py:1066 | general | ALICE |
| R17 | [1/4] | ⚪ | Pre-existing functions over 50 lines (`_create_buvis_options` 113, its decorator 108, wrapper 52), unchanged by this fix. | src/lib/buvis/pybase/configuration/click_integration.py:245 | general | BOB |
| R18 | [1/4] | ⚪ | The test module already exceeded 800 lines before this addition; splitting the existing suite is out of scope. | tests/lib/pybase/configuration/test_click_integration.py:1162 | general | BOB |

## Alice

Consensus lens, implementation-aware. Raised R4 (🔴 sysup/dot regression from the new `_run_update_check_once` signature), R1 and R5 (🟠), R2, R3, R6 (🟡), R14, R15, R16 (⚪).

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
R12: pass
R13: fail

## Blake

Blind lens (PRD only, no diff). Raised R1 (🟠), R7, R8, R9 (🟡) and one ⚪ docs/CHANGELOG note. He independently reached the same `--config-dir` gap from the spec alone.

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

Doubt rubric D1-D5 plus de-slop, codex static sandbox. FIX: R1 (🟠), R10, R11 (🟡). VERIFY: (none). KNOWN: R12, R17, R18.

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

Gemini lens via copilot backend (model gemini-3.8-flash). Raised R1 (🟠), R3 and R13 (🟡). He ran a live `--config-dir` probe against the built package.

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

Verdict: 18 findings
Tests: 677 passed, 0 failed, 0 skipped (exit 0) (suite run this cycle)

Test-gate scope note (fail loud): the gate command for this cycle was the touched-area scope `pytest tests/lib/pybase/configuration tests/lib/pybase/updater`, not the whole suite, because the repo's full suite needs sandbox env pinning and carries unrelated red. That narrow green is exactly what hid R4: the full run of `tests/tools/sysup tests/tools/dot` at this HEAD is `86 failed, 1711 passed, 10 skipped, 1 xfailed, 10 errors`, with 76 `TypeError` lines caused by this diff.
