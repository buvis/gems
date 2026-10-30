---
prd: docs/dev/project-management/prds/wip/00110-backup-plan-preview-and-output-resolution-v1.md
review: 1
date: 2026-10-30
head_sha: 5c4f455f95c89447158b5536de68d561d1fc49ca
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: disabled
dispatch_rows:
  bob: 5941fa83
---

# Review: 00110-backup-plan-preview-and-output-resolution-v1

Diff range: `7f4b462f1275c9306d7cc452cb2024a429f2c371..5c4f455f95c89447158b5536de68d561d1fc49ca`

codex_rung_guard: not fired
autocodex_alice_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00110-c1-alice-anthropic.txt.receipt.json
autocodex_blake_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00110-c1-blake-anthropic.txt.receipt.json
autocodex_bob_anthropic_receipt: /Users/bob/git/src/github.com/buvis/gems/docs/dev/project-management/autopilot/reports/00110-c1-bob-anthropic.txt.receipt.json
provider_review_guard: satisfied

The model-provider guard supersedes the legacy launcher guard; Eve did not run. All three isolated reviews served claude-opus-5-5 at xhigh. Implementation was OpenAI gpt-6.1-sol plus gpt-6-astra; the original model audit remains the reviewed snapshot.

## Review Summary

Reviewed all five completed tasks and the full PRD work range. Alice, Blake, and Bob completed with validated receipts. Blake received only PRD/rubric/repository access and test result, with no diff, plan, history, implementation audit, or sibling findings. Bob received the complete inline context/diff, full consensus rubric, doubt D1-D5 and de-slop appendix.

Carl: disabled after automatic approval review denied optional Gemini/Copilot repository egress; no backend ran. No permission or nesting guard was changed.

Context pack: failed (engram pack timed out after 300s). All mandatory lenses completed without the pack. Staging errors: none. Fail-first replay: three new test files fail collection against the base because required interfaces are absent; zero pre-change passing tests. Tautological shapes: none among 50 test functions.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Found By |
|-----|-----------|----------|-------|------|----------|
| R1 | [3/3] | 🟠 | `Runner.run` now calls `_plan`/`capability.plan` before `_run_instance` and outside its `try/except` (src/tools/backup/runner.py:36). Any OSError from the new metadata checks escapes the generator: `out.exists()`, `is_dir`, `is_symlink`, or a RuntimeError from `resolve` on a symlink loop. `_run_plan` in src/tools/backup/cli.py catches only `FatalError`, so the user sees a raw traceback and every other selected instance is skipped. I reproduced it with one instance whose `out` sits under a chmod-000 dir, plus one good instance. At base 7f4b462 that step fails ("bad failed: [Errno 13] …") and the good instance still archives. At HEAD the run dies with PermissionError and no archive is written. `--plan` crashes the same way. No test covers this. Fix: catch per instance in `_plan` and turn the error into a `fail` entry, the same way `_run_instance` handles it. | src/tools/backup/runner.py:36 | ALICE, BLAKE, BOB |
| R2 | [3/3] | 🟡 | `TarArchive.plan` resolves `engine` without `run`'s `or _ENGINE_PYTHON` fallback. `engine: ""` now plans as `fail "unknown engine ''"`, and `Runner.run` stops on any plan `fail`. So a config that base archived with python-tarfile (reproduced) now fails in run and in `--dry-run`. That breaks the PRD rule "`--dry-run` is unchanged". | src/tools/backup/capabilities/tar_archive.py:80 | ALICE, BLAKE, BOB |
| R3 | [3/3] | 🟡 | `plan` lacks `run`'s "no source configured" / "no out path configured" guard. An empty `source` plans as `run` with source `.` (the cwd) and exits 0, while the real run fails (reproduced). An empty `out` resolves to `.` with `[replaces existing]`, and two empty outs get reported as a duplicate collision. The preview does not match what a run would do. | src/tools/backup/capabilities/tar_archive.py:78 | ALICE, BLAKE, BOB |
| R4 | [1/3] | 🟡 | Simplification: `plan` copies `run`'s pre-walk checks one by one: the engine check with the message repeated word for word at tar_archive.py:87 and :136, the source is_dir/exists branch, the containment check, and `_normalize_items`. That copy is how the two drifts above crept in. Move the checks into one shared validator that returns (status, reason) and call it from both `plan` and `run`. | src/tools/backup/capabilities/tar_archive.py:76 | ALICE |
| R5 | [1/3] | 🟡 | Simplification: `Runner._plan` (runner.py:54-59) and `_run_instance` (runner.py:82-88) build the same `call_kwargs` dict; only `dry_run` differs. Use one `_call_kwargs(name, instance, now)` helper and add `dry_run` at the call site. | src/tools/backup/runner.py:54 | ALICE |
| R6 | [2/3] | ⚪ | `_plan` tests `capability is None` twice (runner.py:51 and :62, the second with `continue`). Move `outputs.setdefault(...)` into the `else` branch and drop the second check. Additional wording: `_plan` computes `os.path.normpath(os.path.expanduser(entry.out))` twice per entry, and it checks `capability is None` twice. Computing the key once in the first loop removes both repeats. | src/tools/backup/runner.py:62 | ALICE, BOB |
| R7 | [2/3] | ⚪ | `_run_validated` re-reads `label` and `engine` from kwargs (tar_archive.py:161-162), though `run` already computed both. Pass them as parameters instead. Additional wording: `_run_validated` parses `label` and `engine` from `kwargs` again, though `run()` already parsed them. `plan()` and `run()` also repeat the same source/out/`cast(now)` setup. This duplication is how the engine `""` drift happened. | src/tools/backup/capabilities/tar_archive.py:161 | ALICE, BOB |
| R8 | [1/3] | ⚪ | The test builds its expected `reason` by calling `TarArchive().plan(...)`, the code under test, so it can never catch a wrong reason on a `run` row. Assert `""` instead. | tests/tools/backup/test_plan_runner.py:237 | ALICE |
| R9 | [2/3] | ⚪ | The duplicate check compares paths as text only, as the spec says. It misses two names for one file on case-insensitive APFS (`~/Backup/x.tgz` vs `~/backup/x.tgz`) and a relative vs absolute spelling of the same file (`x.tgz` vs `$PWD/x.tgz`). So two instances can still write one archive and race. The docs mention only symlinks as not resolved. | src/tools/backup/runner.py:64 | BLAKE, BOB |
| R10 | [1/3] | ⚪ | `replaces` uses `out.exists()`, which follows symlinks. A dangling symlink at `out` reports `replaces=False` even though `os.replace` will overwrite it. The rest of plan uses `lexists`, so this is inconsistent. | src/tools/backup/capabilities/tar_archive.py:81 | BOB |
| R11 | [1/3] | ⚪ | The `_run_plan` docstring still says it only runs and renders steps. It does not mention the `plan_only` branch that prints plan rows and never executes anything. | src/tools/backup/cli.py:203 | BOB |
| R12 | [1/3] | ⚪ | Unconfirmed whether README.md documents backup CLI flags. The capsule invariant says every CLI change updates README.md, but only backup.rst and CHANGELOG.md were touched. | README.md | BOB |
| R13 | [1/3] | ⚪ | Known limitation: the plan's item check ignores exclusions. If every present item is excluded, the plan shows `run` but the actual run skips. The PRD specifies a lexists-only check. | src/tools/backup/capabilities/tar_archive.py:76 | BOB |

## Consolidation corrections

The consolidation script succeeded, but merged unrelated Runner simplification findings into the exception defect and left duplicate root causes separate by citation. The table was corrected against every raw issue line: the two Runner simplifications remain distinct rows, Blake's second exception citation is included in the first defect, repeated parsing is one issue, and both lexical-limit observations are retained together. No raw issue or rubric verdict was dropped. Original script output is retained in the evidence report.

## Alice

Independent Anthropic review; raw output preserved verbatim below.

### Anthropic

[ALICE] 🟠 `Runner.run` now calls `_plan`/`capability.plan` before `_run_instance` and outside its `try/except` (src/tools/backup/runner.py:36). Any OSError from the new metadata checks escapes the generator: `out.exists()`, `is_dir`, `is_symlink`, or a RuntimeError from `resolve` on a symlink loop. `_run_plan` in src/tools/backup/cli.py catches only `FatalError`, so the user sees a raw traceback and every other selected instance is skipped. I reproduced it with one instance whose `out` sits under a chmod-000 dir, plus one good instance. At base 7f4b462 that step fails ("bad failed: [Errno 13] …") and the good instance still archives. At HEAD the run dies with PermissionError and no archive is written. `--plan` crashes the same way. No test covers this. Fix: catch per instance in `_plan` and turn the error into a `fail` entry, the same way `_run_instance` handles it. | File: src/tools/backup/runner.py:36 | Task: 3
[ALICE] 🟡 `TarArchive.plan` resolves `engine` without `run`'s `or _ENGINE_PYTHON` fallback. `engine: ""` now plans as `fail "unknown engine ''"`, and `Runner.run` stops on any plan `fail`. So a config that base archived with python-tarfile (reproduced) now fails in run and in `--dry-run`. That breaks the PRD rule "`--dry-run` is unchanged". | File: src/tools/backup/capabilities/tar_archive.py:80 | Task: 2
[ALICE] 🟡 `plan` lacks `run`'s "no source configured" / "no out path configured" guard. An empty `source` plans as `run` with source `.` (the cwd) and exits 0, while the real run fails (reproduced). An empty `out` resolves to `.` with `[replaces existing]`, and two empty outs get reported as a duplicate collision. The preview does not match what a run would do. | File: src/tools/backup/capabilities/tar_archive.py:78 | Task: 2
[ALICE] 🟡 Simplification: `plan` copies `run`'s pre-walk checks one by one: the engine check with the message repeated word for word at tar_archive.py:87 and :136, the source is_dir/exists branch, the containment check, and `_normalize_items`. That copy is how the two drifts above crept in. Move the checks into one shared validator that returns (status, reason) and call it from both `plan` and `run`. | File: src/tools/backup/capabilities/tar_archive.py:76 | Task: 2
[ALICE] 🟡 Simplification: `Runner._plan` (runner.py:54-59) and `_run_instance` (runner.py:82-88) build the same `call_kwargs` dict; only `dry_run` differs. Use one `_call_kwargs(name, instance, now)` helper and add `dry_run` at the call site. | File: src/tools/backup/runner.py:54 | Task: 3
[ALICE] ⚪ `_plan` tests `capability is None` twice (runner.py:51 and :62, the second with `continue`). Move `outputs.setdefault(...)` into the `else` branch and drop the second check. | File: src/tools/backup/runner.py:62 | Task: 3
[ALICE] ⚪ `_run_validated` re-reads `label` and `engine` from kwargs (tar_archive.py:161-162), though `run` already computed both. Pass them as parameters instead. | File: src/tools/backup/capabilities/tar_archive.py:161 | Task: 2
[ALICE] ⚪ The test builds its expected `reason` by calling `TarArchive().plan(...)`, the code under test, so it can never catch a wrong reason on a `run` row. Assert `""` instead. | File: tests/tools/backup/test_plan_runner.py:237 | Task: 3

R1: pass
R2: pass
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

Independent Anthropic review; raw output preserved verbatim below.

### Anthropic

[BLAKE] 🟠 Planning now runs before every normal run and dry-run, and nothing guards it. One instance whose source or out path raises an `OSError` on `stat` (for example, a parent dir with no read access gives `PermissionError` from `is_dir()` or `exists()`) aborts the whole run before any instance archives. The error then reaches the user as a raw traceback, because `_run_plan` catches only `FatalError`. Before this change the runner caught the exception and turned it into one failed step, which is still what the `Capability` docstring promises. I reproduced it: with a healthy `a-good` and an unreadable `b-locked`, both `--plan` and a plain run exited 1 with an uncaught `PermissionError`, and `good.tgz` was never written. This also breaks "`--dry-run` is unchanged". | File: src/tools/backup/runner.py:36 | Task: general
[BLAKE] 🟠 The calls that raise are `out.exists()`, `source.is_dir()` and the `is_symlink()` calls in `_normalize_items` during planning, and `_plan` has no try/except for them, so an `OSError` from one instance kills the batch. Same root cause as the finding above. | File: src/tools/backup/capabilities/tar_archive.py:81 | Task: general
[BLAKE] 🟡 `plan` and `run` treat an empty engine differently. `plan` reads `engine` without the `or _ENGINE_PYTHON` fallback that `run` uses (tar_archive.py:114). So `engine: ""` makes `plan` say `fail` ("unknown engine ''") while `TarArchive.run` archives with the python engine. `Runner.run` now skips any instance `plan` marks as failed, so a config that used to run now fails in both normal runs and `--dry-run`. Reproduced. | File: src/tools/backup/capabilities/tar_archive.py:80 | Task: general
[BLAKE] 🟡 `plan` reports `run` for an instance whose run is certain to fail. An empty `source` becomes `.` (the cwd, which is a directory), so `plan` says `run . -> <out>` while `run` fails with "no source configured". An empty `out` becomes `.`, so `plan` says `run ... -> .  [replaces existing]` while `run` fails with "no out path configured". The preview is not safe for misconfigured instances. Reproduced. | File: src/tools/backup/capabilities/tar_archive.py:78 | Task: general
[BLAKE] ⚪ The duplicate check compares paths as text only, as the spec says. It misses two names for one file on case-insensitive APFS (`~/Backup/x.tgz` vs `~/backup/x.tgz`) and a relative vs absolute spelling of the same file (`x.tgz` vs `$PWD/x.tgz`). So two instances can still write one archive and race. The docs mention only symlinks as not resolved. | File: src/tools/backup/runner.py:64 | Task: general

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
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

What I checked:
- **Tests:** `tests/tools/backup/test_plan.py` passes (105 tests). The `-k "runner or duplicate"` subset passes (4 selected) and the `-k cli` subset passes (1 selected).
- **Spec match:** the `PlanEntry` fields, row format, duplicate message, the `--plan`/`--dry-run` mutual exclusion, the one-timestamp-per-run rule, the docs and the CHANGELOG entry all match the spec.
- **Vacuous rules:** B17, B18 and B19 pass only because the PRD has no Phase 3 and no out-of-scope section.
- **Temp leftovers:** my probe runs left a few small `blake-*` folders in the macOS temp dir. They are harmless, and I deleted only my two probe scripts.

## Bob

Independent Anthropic review; raw output preserved verbatim below.

### Anthropic

[BOB] 🟠 `Runner._plan` calls `capability.plan()` with no exception guard, so one instance can abort the whole run or plan. Before this change, `_run_instance` turned an instance's exception into a failed step and the other instances still ran. Now an `OSError` from planning one instance stops every instance before any work starts. Examples: `out.exists()` or `source.is_dir()` raising `EACCES` or `EIO` on a dead mount, which they do on 3.11 and 3.12. The traceback reaches the user because the CLI catches only `FatalError`. This breaks the `Capability` docstring ("any other exception is caught by the runner and turned into a failed step") and the AGENTS.md "no raw tracebacks" rule. | File: src/tools/backup/runner.py:60 | Task: 3
[BOB] 🟡 `TarArchive.plan` does not repeat `run()`'s empty-input checks ("no source configured" / "no out path configured"). An instance with no `source` normalizes to `.`, which is a directory, so `--plan` shows `run  . -> <out>` and exits 0 for an instance that will fail. In a real run, two instances with no `out` both normalize to `.` and get a misleading collision message on `.`. | File: src/tools/backup/capabilities/tar_archive.py:78 | Task: 2
[BOB] 🟡 Plan and run disagree on engine `""`. `plan()` reads it with `_require_str(..., default=_ENGINE_PYTHON)` and no `or _ENGINE_PYTHON` fallback, so `""` fails. `run()` treats `""` as the python engine. Because `Runner.run` now refuses to execute anything `plan()` marks `fail`, a config with `engine: ""` that used to run or dry-run now fails. The PRD says "`--dry-run` is unchanged". Test test_plan.py:391 locks in the divergent behavior with its `("", "fail")` row. | File: src/tools/backup/capabilities/tar_archive.py:80 | Task: 2
[BOB] ⚪ `replaces` uses `out.exists()`, which follows symlinks. A dangling symlink at `out` reports `replaces=False` even though `os.replace` will overwrite it. The rest of plan uses `lexists`, so this is inconsistent. | File: src/tools/backup/capabilities/tar_archive.py:81 | Task: 2
[BOB] ⚪ The `_run_plan` docstring still says it only runs and renders steps. It does not mention the `plan_only` branch that prints plan rows and never executes anything. | File: src/tools/backup/cli.py:203 | Task: 4
[BOB] ⚪ `_plan` computes `os.path.normpath(os.path.expanduser(entry.out))` twice per entry, and it checks `capability is None` twice. Computing the key once in the first loop removes both repeats. | File: src/tools/backup/runner.py:68 | Task: 3
[BOB] ⚪ `_run_validated` parses `label` and `engine` from `kwargs` again, though `run()` already parsed them. `plan()` and `run()` also repeat the same source/out/`cast(now)` setup. This duplication is how the engine `""` drift happened. | File: src/tools/backup/capabilities/tar_archive.py:161 | Task: 2
[BOB] ⚪ Unconfirmed whether README.md documents backup CLI flags. The capsule invariant says every CLI change updates README.md, but only backup.rst and CHANGELOG.md were touched. | File: README.md | Task: 5
[BOB] ⚪ Known limitation: the collision check is lexical only. A relative and an absolute path to the same file are not caught, and neither are paths that differ only in case on a case-insensitive filesystem. The PRD requires normpath, and the docs state the limit. | File: src/tools/backup/runner.py:64 | Task: 3
[BOB] ⚪ Known limitation: the plan's item check ignores exclusions. If every present item is excluded, the plan shows `run` but the actual run skips. The PRD specifies a lexists-only check. | File: src/tools/backup/capabilities/tar_archive.py:76 | Task: 2

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: fail
R11: pass
R12: pass
R13: pass

FIX:
- `capability.plan()` exceptions escape `Runner._plan` and abort every instance with a traceback — src/tools/backup/runner.py:60 — wrap the `capability.plan(**call_kwargs)` call in `try`/`except FatalError: raise`/`except Exception as exc:`, and produce `PlanEntry(name, "", "", "fail", f"{name} failed: {exc}", False)`, which matches the old `_run_instance` message. Add a regression test where `out.exists` raises `PermissionError` for one instance and the other instance still runs.
- Plan reports `run` for instances with no source or out — src/tools/backup/capabilities/tar_archive.py:78 — before resolving paths, check the raw strings the way `run()` does and return a `fail` entry with "no source configured" or "no out path configured". In `Runner._plan`, leave entries with an empty `out` out of collision grouping.
- `plan()` rejects engine `""` while `run()` accepts it — src/tools/backup/capabilities/tar_archive.py:80 — add `or _ENGINE_PYTHON` as `run()` does, and change the `("", "fail")` row in test_plan.py:391 to `run`.
- `replaces` follows symlinks — src/tools/backup/capabilities/tar_archive.py:81 — use `os.path.lexists(out)`.
- Stale `_run_plan` docstring — src/tools/backup/cli.py:203 — mention the `plan_only` branch and its fail-based return value.
- Double normalization and double `None` check in `_plan` — src/tools/backup/runner.py:68 — compute the key once in the first loop, store `(entry, key)` pairs, and reuse them.
- `_run_validated` re-parses `label` and `engine`, and plan/run repeat the path setup — src/tools/backup/capabilities/tar_archive.py:161 — pass the parsed values through, or extract one small `_resolve_paths(kwargs)` helper that both methods call.
VERIFY:
- Does README.md document backup flags and need a `--plan` line? — run `rg -n -- "--dry-run|--show-excludes|backup " README.md`. If it lists backup flags, add `--plan`.
KNOWN:
- The lexical collision check misses relative-vs-absolute and case-only differences — the PRD requires `os.path.normpath`, and the docs say symlinks are not resolved.
- The plan's item check ignores exclusions — the PRD limits plan to lexists/is_dir/stat, and the risk section notes that execution checks everything again.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Decision Gate

Independent temporary-fixture probes confirmed the uncaught planning PermissionError prevents the healthy archive; empty engine plans fail while direct dry-run succeeds; empty source/out plan as run. These are bounded regressions, not an API or data-model decision. No CRITICAL or security/data-loss finding was raised. Cycle 1 is below cap 2.

- R1: fix — bounded supported defect or repeated simplification; queue first-pass regression follow-up.
- R2: fix — bounded supported defect or repeated simplification; queue first-pass regression follow-up.
- R3: fix — bounded supported defect or repeated simplification; queue first-pass regression follow-up.
- R4: discard — single-voice.
- R5: discard — single-voice.
- R6: fix — bounded supported defect or repeated simplification; queue first-pass regression follow-up.
- R7: fix — bounded supported defect or repeated simplification; queue first-pass regression follow-up.
- R8: discard — single-voice.
- R9: discard — specified lexical normpath behavior; broader file identity is outside PRD scope.
- R10: discard — single-voice.
- R11: discard — single-voice.
- R12: discard — README lists the tool only; it does not enumerate backup flags; rg inspection refuted missing flag documentation.
- R13: discard — single-voice.

R12 VERIFY was not queued: command shape (ad hoc README inspection, not a project test/lint/build/type-check gate). Direct `rg -n -- "--dry-run|--show-excludes|backup " README.md` returned only the generic backup tool table at line 94. The README does not enumerate these flags.

The accepted changes are narrow new decision-gate follow-ups; no original-plan task is being redone. All original attempt provenance and the receipt-bound snapshot stay unchanged. The grouper owns task boundaries. No repair runs in this review session.

## Verification

Review-stage gate: uv run pytest, process exit 0; 6003 passed, 16 skipped, 1 xfailed, 317 warnings in 143.50s. Required canonical verify fallback: uv run pytest -q --tb=line, process exit 0; same counts in 159.81s. Both canonical calls returned unparsed counts; no last-verification.json was manually created. The Tests line below transcribes observed counts, with xfailed kept separately. Ruff passed; mypy passed for 11 backup source files.

## Rework handoff

The decision-gate batch atomically created tasks 6 and 7 at logical Sonnet. Task 6 owns runner exception isolation and repeated normalization/None checks; task 7 owns empty input/engine compatibility and repeated parsing. Both retain every quoted finding. Original tasks 1–5 and all attempts remain unchanged. The review is not converged. Phase/next_phase stay review, cycle stays 1, and the next fresh session resumes Phase 6 Dispatch rework. It must complete only rework_task_ids 6 and 7 through the full source work pipeline, then use phase-done --outcome rework to advance to cycle 2 and exit. No completion gate or repairs ran here.

Validation: source review shape/findings coverage passed; adapter.review_gap returned None after validating all three receipts and complete source rubrics; schema/task counts passed (5 completed of 7); only the main worktree exists. The source review-close optional lost/skipped lens labels were removed through statectl to retain only the actual completed consensus/blind/doubt roster.

Verdict: 13 findings
Tests: 6003 passed, 0 failed, 16 skipped (suite run this cycle; 1 xfailed; raw pytest counts, canonical parser unparsed, no cache record)
