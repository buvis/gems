---
prd: docs/dev/project-management/prds/wip/00136-sysup-plan-config-errors-raw-v1.md
review: 1
date: 2026-11-13
head_sha: 3c8a1671e60c7a1ea1df3a73f422294c0da16bcd
codex_thread_id: 01a1d67c-46ec-7790-a9da-5aaec43f8bde
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: ab95f70a
  carl: 783ee357
---

# Review: 00136-sysup-plan-config-errors-raw-v1

Diff range: `8579ffeb003d9acf8b616fb6670bcc02e5f43b3b..3c8a1671e60c7a1ea1df3a73f422294c0da16bcd`

codex_rung_guard: not fired

pack: failed (engram pack exit 1: not inside a registered repo)

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00136-sysup-plan-config-errors-raw-v1

### Agent Status

- Alice: ✅ Available (native Claude subagent, consensus lens)
- Blake: ✅ Available (native Claude subagent, blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt lens D1-D5 + de-slop)
- Carl: ✅ Available (gemini CLI, frontend/design specialist, generalist here)
- Eve: ⏸️ Disabled (doubt_reviewer is `codex`, codex rung guard not fired)

Consolidation ran through `consolidate_findings.py` (no ledger — cycle 1). Its
file-plus-text matcher did not fold four rows that describe one defect, because
each reviewer cited a different file:line for it; the decision gate treats
R4 + R6 + R7 + R11 as ONE finding raised by three reviewers (Bob, Carl, Blake)
and R3 + R12 as one raised by two (Bob, Blake). That regrouping is a gate
judgment call, recorded here so it is visible rather than silent.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟡 | Sysup's new `_merge_layer` path for a malformed YAML file, an unset `${VAR}` and an unreadable file (`yaml.YAMLError`, `MissingEnvVarError`, `OSError`, `UnicodeError` become a `FatalError` starting with the file path) has no test. Only the directive-on-mapping and type-error paths are covered. | src/tools/sysup/config.py:324 | 1 | ALICE |
| R2 | [1/4] | 🟡 | `_format_validation_errors`, `_merge_layer` and the key-source bookkeeping are copied almost line for line between the two tools; the new code repeats the same ~40 lines, which will drift. Move the shared parts into `buvis.pybase.configuration`. | src/tools/backup/config.py:146 | 2 | ALICE |
| R3 | [1/4] | 🟡 | Source tracking misattributes inherited errors when two files modify the same mapping entry: an invalid `commands.custom.order` in `config.yaml` is blamed on `buvis-sysup.yaml` when that file only changes `commands.custom.steps`. Track sources by nested field path in both loaders. | src/tools/sysup/config.py:355 | general | BOB |
| R4 | [1/4] | 🟡 | The load-time exception handlers omit `ConfigurationError`, so that exception from `load_yaml` escapes instead of becoming a file-qualified `FatalError`. Add it to both handlers and cover this error path. | src/tools/sysup/config.py:330 | general | BOB |
| R5 | [1/4] | 🟡 | The `ntfy` error test passes against the previous raw pydantic error: it already contains `ntfy` and omits `prime`. Assert the supplying file and the absence of pydantic URLs to bind this test to the required improvement. | tests/tools/sysup/test_plan_config_errors.py:138 | 1 | BOB |
| R6 | [1/4] | 🟡 | ConfigurationError from load_yaml is not caught and converted to FatalError | src/tools/sysup/config.py:329 | 1 | CARL |
| R7 | [1/4] | 🟡 | ConfigurationError from load_yaml is not caught and converted to FatalError | src/tools/backup/config.py:173 | 2 | CARL |
| R8 | [1/4] | 🟡 | Recomputing the set union of the backup top-level and settings key sets inside the loop; precompute `allowed` before the loop as sysup does. | src/tools/backup/config.py:54 | 2 | CARL |
| R9 | [1/4] | ⚪ | Backup tests `test_shared_config_*` and `test_typo_key_names_file_and_key` pass against the pre-change code. That fits the PRD's "confirm" wording for task 2, but they act as characterization tests, not regression tests. | tests/tools/backup/test_plan_config_errors.py:17 | 2 | ALICE |
| R10 | [1/4] | ⚪ | Sysup's `_load_default()` failures (bundled YAML load) are not wrapped in `FatalError`, while backup's equivalent is. Unreachable in practice, but the two loaders differ. | src/tools/sysup/config.py:388 | 1 | ALICE |
| R11 | [1/4] | ⚪ | `load_config` lets `ConfigurationError` escape for a non-mapping YAML root; a direct `load_config(config_dir=...)` call on a `buvis-sysup.yaml` containing `- a` gives a raw traceback. Through the CLI the settings resolver reports it first (exit 1, one console line), so users never see it, but the docstring claim "never a raw traceback" is false and `src/tools/sysup/cli.py:175` catches only `FatalError`. | src/tools/sysup/config.py:329 | 1 | BLAKE |
| R12 | [1/4] | ⚪ | Error attribution is last-writer-wins per top-level key and per `commands.<name>` / `expiry.<name>` entry: when two layers set different fields of the same entry, the error names the later file. The tests cover only distinct entries per file. | src/tools/sysup/config.py:352 | 1 | BLAKE |
| R13 | [1/4] | ⚪ | The sysup and backup `_merge_layer` use different wording for a failed file load; backup's `known_keys={"excludes"}` typo guard has no sysup counterpart, and `SysupSettings.config_deferred_keys` is hand-maintained and can drift from `SysupConfig.model_fields`. None of these breaks the spec. | src/tools/sysup/settings.py:11 | 1 | BLAKE |

No 🔴 CRITICAL and no 🟠 HIGH finding was raised by any lens.

## Alice

Consensus lens, implementation-aware. Four findings (R1, R2, R9, R10). Verdicts:

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

## Blake

Blind lens, PRD-only prompt; he located the code himself and probed the CLI.
Three findings (R11, R12, R13), all ⚪.

Verified by him: the merged-layer projection onto `SysupConfig`, the surviving
typo check for `buvis-sysup*.yaml`, list directives (`commands-` / `expiry-`)
wrapped as a file-qualified `FatalError`, pydantic type errors rendered as one
console line with no pydantic URL and exit 1, global `debug` / `log_level`
accepted in `buvis-sysup.yaml`, the backup shared-key case, and the CHANGELOG
entries for both tools. He ran the two new test files plus both existing
`test_config.py` files (89 passed) and did not re-run the full suite. He could
not check fail-first against the old code.

B1-B19: all pass.

## Bob

Doubt lens (codex), rubric D1-D5 plus de-slop. FIX: R3, R4, R5. VERIFY: none.
KNOWN: none. No verification-check queue was written this cycle (empty VERIFY
bucket, and Eve did not run).

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini CLI (`gemini` backend), exit 0. Three findings (R6, R7, R8). All R
verdicts pass.

## Test gate

The host's git configuration enables ssh commit signing through the 1Password
agent, and that agent is locked in this session: the `dot` pull-divergence
tests commit in throwaway repos and failed `git commit` with exit 128
(`error: 1Password: agent returned an error`), showing up as 10 setup errors
unrelated to this PRD's diff. Isolating the global and system git config for
the gate run (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_SYSTEM=/dev/null`)
removes them; the gate then passes clean. This is an environment fix in the
gate wrapper only — no repository file was changed for it.

Verdict: 13 findings
Tests: 7551 passed, 0 failed, 17 skipped (suite run this cycle)
