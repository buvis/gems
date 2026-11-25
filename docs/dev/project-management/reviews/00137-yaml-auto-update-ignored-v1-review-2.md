---
prd: docs/dev/project-management/prds/wip/00137-yaml-auto-update-ignored-v1.md
review: 2
date: 2026-11-13
head_sha: 05519078a37e36baa364f44550368a14b3aacde2
codex_thread_id: 01a1d6b7-edf2-7290-903b-1a89ba543ee3
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 0a79ab3b
  carl: 078d5c59
---

# Review: 00137-yaml-auto-update-ignored-v1

Diff range: `28a0580dc7c736e9654bf5a2b1abcdaaa8abc490..05519078a37e36baa364f44550368a14b3aacde2` (incremental — cycle 1 reviewed the full `8d98134f..28a0580d` range)

codex_rung_guard: not fired

pack: failed (engram pack exit 1: worktree not registered with gita) - cycle degraded, not invalid.
replay: skipped (fail-first runner exit 4: ModuleNotFoundError: No module named 'inflection'), so no mechanical replay evidence this cycle.
mechanical test checks: no `[MECH]` lines this cycle (16 test functions in 2 files checked).

## Review Summary

### Agent Status

- alice: available (Claude subagent, consensus lens)
- blake: available (Claude subagent, blind/PRD-only lens)
- bob: available (codex, doubt rubric D1-D5 + de-slop; codex thread resumed from cycle 1)
- carl: available (copilot backend, model gemini-3.8-flash)
- eve: disabled (doubt_reviewer is codex and no task was implemented by codex, so the codex doubt-roster guard did not fire)

### Prior-cycle closure

Both cycle-1 CRITICALs are closed and confirmed by Alice independently: the sysup stub arity (`tests/tools/sysup/conftest.py:20` now `lambda _ctx, _args`, guarded by `tests/tools/sysup/test_cli_update_hook.py`) and the restored global `BUVIS_AUTO_UPDATE` read. `--config-dir` (R1), last-wins extraction (R10), the narrowed suppression (R8) and the test-coverage gap (R3) are all resolved. Cycle 1's R2 (docs overclaim) is only partly closed — the replacement sentence carries the env-`true` inaccuracy raised as R3/R4 below.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟠 | The global fallback changes `enabled` without changing the settings passed to the updater. With `FooSettings`, `BUVIS_AUTO_UPDATE=true`, and YAML `auto_update: false`, the updater receives `settings.auto_update=False` despite the enabled decision. Pass a settings copy containing the effective `auto_update` value. Extend `test_global_env_true_runs_tool_check_despite_yaml_false` to assert that argument; its current call-count assertion misses this contradiction. | src/lib/buvis/pybase/configuration/click_integration.py:210 | 3 | BOB |
| R2 | [1/4] | 🟡 | `_update_enabled` returns True when `BUVIS_AUTO_UPDATE=true` and a tool class has YAML `auto_update: false`, but `check_and_update` returns immediately on `settings.auto_update` False (src/lib/buvis/pybase/updater/__init__.py:47). The global-true branch never starts a check in production; only the global-false direction has any effect. `test_global_env_true_runs_tool_check_despite_yaml_false` passes only because `check_and_update` is mocked, so it pins behaviour the real code never has. Fix: drop the "global true runs the check" claim and test. Keep only the global-false opt-out, or pass an env-aware settings object to the updater. | tests/lib/pybase/configuration/test_click_integration_auto_update.py:99 | 3 | ALICE |
| R3 | [1/4] | 🟡 | PRD Success Metric 2 says "env still wins over YAML". Env `true` against YAML `false` loses: the resolver's `_merge_overrides` treats an env value equal to the field default as unset, so `_update_enabled` returns the YAML `false` for both a tool-prefixed variable and the global one. The new docs sentence ("A tool-prefixed `BUVIS_<TOOL>_AUTO_UPDATE` overrides it") is therefore wrong for `true`. `test_prefixless_settings_class_lets_yaml_decide_over_global_env` pins the opposite of the PRD wording. The design recorded the resolver hole as out of scope. Either narrow the docs sentence to say only `false` overrides, or return `settings_class().auto_update` (env-only) in the prefixed branch so env wins. | docs/source/configuration.rst:830 | 4 | ALICE |
| R4 | [1/4] | 🟡 | "Env still wins over YAML" does not hold for `BUVIS_AUTO_UPDATE=true` with `auto_update: false` in YAML on a prefixless (`GlobalSettings`) class. `ConfigResolver._merge_overrides` cannot tell an env value equal to the default from an unset one, so YAML `false` wins and the check is skipped. This is a pre-existing resolver limitation, and the `false` case in the spec works. The test pins the behaviour as accepted, so it contradicts the literal spec sentence. | src/lib/buvis/pybase/configuration/resolver.py:231 | 1 | BLAKE |
| R5 | [1/4] | ⚪ | The `_run_update_check_once` docstring still says it honours only `--config` and that any resolution failure is suppressed. It now also reads `--config-dir`, applies the global env fallback, and suppresses only a narrow exception tuple. Update the text. | src/lib/buvis/pybase/configuration/click_integration.py:176 | 3 | ALICE |
| R6 | [1/4] | ⚪ | The narrowed `except (ConfigurationError, MissingEnvVarError, ValidationError, OSError)` does not cover `RuntimeError`. `Path.home()` raises it when the home directory cannot be determined, which `loader.py:314` already handles elsewhere. `--help` on such a host would now crash where the old broad suppress degraded quietly. Very unlikely edge case. | src/lib/buvis/pybase/configuration/click_integration.py:200 | 3 | ALICE |
| R7 | [1/4] | ⚪ | The `_update_enabled` fallback to the global `BUVIS_AUTO_UPDATE` for tool-prefixed settings classes is not in the spec. It is justified: the old code read it through `GlobalSettings()`, so dropping it would break the "keeps working" requirement. Listed for scope-creep awareness only. | src/lib/buvis/pybase/configuration/click_integration.py:158 | 1 | BLAKE |
| R8 | [1/4] | ⚪ | The resolution failure handler catches only `ConfigurationError`, `MissingEnvVarError`, `ValidationError` and `OSError`. Any other exception from the resolver, such as a `TypeError` on a malformed merge, would escape `parse_args` as a raw traceback. The wrapper's own resolve has the same exposure, so this is no worse than before. | src/lib/buvis/pybase/configuration/click_integration.py:200 | 1 | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 Spec says to move the update check to run after `ConfigResolver.resolve` in the `buvis_options` wrapper. The implementation leaves it in the `parse_args` patch and resolves settings a second time from raw argv (`--config` / `--config-dir` scraped by `_extract_option_value`). The observable goal is met, but config files are read and parsed twice per run. The scraped argv can also differ from what Click accepts, for example `--config-dir` is validated by Click only after the check has run. | File: src/lib/buvis/pybase/configuration/click_integration.py:173 — single-voice; same settled decision as the double-resolution row (rework design alternative 3), and the design documents the deviation in the docs line

## Alice

[ALICE] 🟡 `_update_enabled` returns True when `BUVIS_AUTO_UPDATE=true` and a tool class has YAML `auto_update: false`, but `check_and_update` returns immediately on `settings.auto_update` False (src/lib/buvis/pybase/updater/__init__.py:47). The global-true branch never starts a check in production; only the global-false direction has any effect. `test_global_env_true_runs_tool_check_despite_yaml_false` passes only because `check_and_update` is mocked, so it pins behaviour the real code never has. | File: tests/lib/pybase/configuration/test_click_integration_auto_update.py:99 | Task: 3
[ALICE] 🟡 PRD Success Metric 2 says "env still wins over YAML". Env `true` against YAML `false` loses; the new docs sentence is therefore wrong for `true`. | File: docs/source/configuration.rst:830 | Task: 4
[ALICE] ⚪ The `_run_update_check_once` docstring is stale (only `--config`, broad suppression). | File: src/lib/buvis/pybase/configuration/click_integration.py:176 | Task: 3
[ALICE] ⚪ The narrowed except tuple does not cover `RuntimeError` from `Path.home()`. | File: src/lib/buvis/pybase/configuration/click_integration.py:200 | Task: 3

Prior-finding closure: R4 (sysup stub arity) resolved with the smoke guard; R1 (`--config-dir`) resolved via `_extract_option_value` plus the empty-value guard; R10 (last-wins) resolved; R8 (broad suppress) narrowed with `check_and_update` deliberately still guarded; R3 (test gaps) resolved in the new module; R2 (docs) only partly closed. Ran the new module plus the sysup hook test: 21 passed.

R1: pass
R2: fail
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

[BLAKE] 🟡 Spec says to move the update check after `ConfigResolver.resolve` in the wrapper; the implementation keeps it in the `parse_args` patch and resolves a second time from raw argv. | File: src/lib/buvis/pybase/configuration/click_integration.py:173 | Task: 1 — auto-dismissed (ledger, single-voice settled decision)
[BLAKE] 🟡 "Env still wins over YAML" does not hold for `BUVIS_AUTO_UPDATE=true` against YAML `false` on a prefixless class; `_merge_overrides` cannot distinguish an env value equal to the default from unset. | File: src/lib/buvis/pybase/configuration/resolver.py:231 | Task: 1
[BLAKE] ⚪ The global-env fallback for tool-prefixed classes is not in the spec, but is justified by the "keeps working" requirement. | File: src/lib/buvis/pybase/configuration/click_integration.py:158 | Task: 1
[BLAKE] ⚪ The resolution failure handler's exception tuple leaves other exception types escaping `parse_args`. | File: src/lib/buvis/pybase/configuration/click_integration.py:200 | Task: 1

Verified from the spec alone: the check resolves through `ConfigResolver` before `check_and_update`; `auto_update: false` in `config.yaml` or `buvis-<tool>.yaml` suppresses it; env `false` suppresses, `true` calls; a failed resolution skips without raising; `BraidSettings` (the PRD's evidence case) is covered; the new 20-test module passes on a narrow run and stubs `check_and_update` so no network is used; `docs/source/configuration.rst:830` and `CHANGELOG.md:28` are updated; no new dependencies or flags.

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

FIX:
- [BOB] 🟠 The global fallback changes `enabled` without changing the settings passed to the updater. With `FooSettings`, `BUVIS_AUTO_UPDATE=true`, and YAML `auto_update: false`, the updater receives `settings.auto_update=False` despite the enabled decision. Pass a settings copy containing the effective `auto_update` value. Extend `test_global_env_true_runs_tool_check_despite_yaml_false` to assert that argument; its current call-count assertion misses this contradiction. | File: src/lib/buvis/pybase/configuration/click_integration.py:210 | Task: 3

VERIFY:
- (none)

KNOWN:
- (none)

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
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

[CARL] ✅ No issues found

Carl exercised the touched test modules, `mypy src/lib/`, the sysup suite and the dot suite, and probed Click's handling of an option value equal to the `--` sentinel; he found nothing to raise.

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
Tests: 2821 passed, 0 failed, 11 skipped (reused from last-verification.json at 1b9f094)
