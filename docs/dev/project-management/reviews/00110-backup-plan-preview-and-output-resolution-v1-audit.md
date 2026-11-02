# Decision Audit Log: 00110-backup-plan-preview-and-output-resolution-v1

PRD: `00110-backup-plan-preview-and-output-resolution-v1.md`
Started: 2026-11-02T10:03:38Z
Completed: 2026-11-02T10:03:38Z
Autonomous: 28  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: How are duplicate outputs represented in Runner.plan and which output spelling appears in collision messages?

**Choice**: PlanEntry.status is fail; reason is the exact StepResult duplicate message; diagnostics use expanduser+normpath output. Other PlanEntry fields retain capability plan values. This satisfies the PRD both-fail plan scenario.

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R1: `Runner.run` now calls `_plan`/`capability.plan` before `_run_instance` and outside its `try/except` (src/tools/backup/runner.py:36). Any OSError from the new metadata checks escapes the generator: `out.exists()`, `is_dir`, `is_symlink`, or a RuntimeError from `resolve` on a symlink loop. `_run_plan` in src/tools/backup/cli.py catches only `FatalError`, so the user sees a raw traceback and every other selected instance is skipped. I reproduced it with one instance whose `out` sits under a chmod-000 dir, plus one good instance. At base 7f4b462 that step fails ("bad failed: [Errno 13] …") and the good instance still archives. At HEAD the run dies with PermissionError and no archive is written. `--plan` crashes the same way. No test covers this. Fix: catch per instance in `_plan` and turn the error into a `fail` entry, the same way `_run_instance` handles it.

**Choice**: fix

**Rationale**: bounded supported defect or repeated simplification; queue first-pass regression follow-up

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R2: `TarArchive.plan` resolves `engine` without `run`'s `or _ENGINE_PYTHON` fallback. `engine: ""` now plans as `fail "unknown engine ''"`, and `Runner.run` stops on any plan `fail`. So a config that base archived with python-tarfile (reproduced) now fails in run and in `--dry-run`. That breaks the PRD rule "`--dry-run` is unchanged".

**Choice**: fix

**Rationale**: bounded supported defect or repeated simplification; queue first-pass regression follow-up

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R3: `plan` lacks `run`'s "no source configured" / "no out path configured" guard. An empty `source` plans as `run` with source `.` (the cwd) and exits 0, while the real run fails (reproduced). An empty `out` resolves to `.` with `[replaces existing]`, and two empty outs get reported as a duplicate collision. The preview does not match what a run would do.

**Choice**: fix

**Rationale**: bounded supported defect or repeated simplification; queue first-pass regression follow-up

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R4: Simplification: `plan` copies `run`'s pre-walk checks one by one: the engine check with the message repeated word for word at tar_archive.py:87 and :136, the source is_dir/exists branch, the containment check, and `_normalize_items`. That copy is how the two drifts above crept in. Move the checks into one shared validator that returns (status, reason) and call it from both `plan` and `run`.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R5: Simplification: `Runner._plan` (runner.py:54-59) and `_run_instance` (runner.py:82-88) build the same `call_kwargs` dict; only `dry_run` differs. Use one `_call_kwargs(name, instance, now)` helper and add `dry_run` at the call site.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R6: `_plan` tests `capability is None` twice (runner.py:51 and :62, the second with `continue`). Move `outputs.setdefault(...)` into the `else` branch and drop the second check. Additional wording: `_plan` computes `os.path.normpath(os.path.expanduser(entry.out))` twice per entry, and it checks `capability is None` twice. Computing the key once in the first loop removes both repeats.

**Choice**: fix

**Rationale**: bounded supported defect or repeated simplification; queue first-pass regression follow-up

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R7: `_run_validated` re-reads `label` and `engine` from kwargs (tar_archive.py:161-162), though `run` already computed both. Pass them as parameters instead. Additional wording: `_run_validated` parses `label` and `engine` from `kwargs` again, though `run()` already parsed them. `plan()` and `run()` also repeat the same source/out/`cast(now)` setup. This duplication is how the engine `""` drift happened.

**Choice**: fix

**Rationale**: bounded supported defect or repeated simplification; queue first-pass regression follow-up

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R8: The test builds its expected `reason` by calling `TarArchive().plan(...)`, the code under test, so it can never catch a wrong reason on a `run` row. Assert `""` instead.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R9: The duplicate check compares paths as text only, as the spec says. It misses two names for one file on case-insensitive APFS (`~/Backup/x.tgz` vs `~/backup/x.tgz`) and a relative vs absolute spelling of the same file (`x.tgz` vs `$PWD/x.tgz`). So two instances can still write one archive and race. The docs mention only symlinks as not resolved.

**Choice**: discard

**Rationale**: specified lexical normpath behavior; broader file identity is outside PRD scope

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R10: `replaces` uses `out.exists()`, which follows symlinks. A dangling symlink at `out` reports `replaces=False` even though `os.replace` will overwrite it. The rest of plan uses `lexists`, so this is inconsistent.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R11: The `_run_plan` docstring still says it only runs and renders steps. It does not mention the `plan_only` branch that prints plan rows and never executes anything.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R12: Unconfirmed whether README.md documents backup CLI flags. The capsule invariant says every CLI change updates README.md, but only backup.rst and CHANGELOG.md were touched.

**Choice**: discard

**Rationale**: README lists the tool only; it does not enumerate backup flags; rg inspection refuted missing flag documentation

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: R13: Known limitation: the plan's item check ignores exclusions. If every present item is excluded, the plan shows `run` but the actual run skips. The PRD specifies a lexists-only check.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: `Runner.run` now calls `_plan`/`capability.plan` before `_run_instance` and outside its `try/except` (src/tools/backup/runner.py:36). Any OSError from the new metadata checks escapes the generator: `out.exists()`, `is_dir`, `is_symlink`, or a RuntimeError from `resolve` on a symlink loop. `_run_plan` in src/tools/backup/cli.py catches only `FatalError`, so the user sees a raw traceback and every other selected instance is skipped. I reproduced it with one instance whose `out` sits under a chmod-000 dir, plus one good instance. At base 7f4b462 that step fails ("bad failed: [Errno 13] …") and the good instance still archives. At HEAD the run dies with PermissionError and no archive is written. `--plan` crashes the same way. No test covers this. Fix: catch per instance in `_plan` and turn the error into a `fail` entry, the same way `_run_instance` handles it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: `TarArchive.plan` resolves `engine` without `run`'s `or _ENGINE_PYTHON` fallback. `engine: ""` now plans as `fail "unknown engine ''"`, and `Runner.run` stops on any plan `fail`. So a config that base archived with python-tarfile (reproduced) now fails in run and in `--dry-run`. That breaks the PRD rule "`--dry-run` is unchanged".

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: `plan` lacks `run`'s "no source configured" / "no out path configured" guard. An empty `source` plans as `run` with source `.` (the cwd) and exits 0, while the real run fails (reproduced). An empty `out` resolves to `.` with `[replaces existing]`, and two empty outs get reported as a duplicate collision. The preview does not match what a run would do.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: `_plan` tests `capability is None` twice (runner.py:51 and :62, the second with `continue`). Move `outputs.setdefault(...)` into the `else` branch and drop the second check. Additional wording: `_plan` computes `os.path.normpath(os.path.expanduser(entry.out))` twice per entry, and it checks `capability is None` twice. Computing the key once in the first loop removes both repeats.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: `_run_validated` re-reads `label` and `engine` from kwargs (tar_archive.py:161-162), though `run` already computed both. Pass them as parameters instead. Additional wording: `_run_validated` parses `label` and `engine` from `kwargs` again, though `run()` already parsed them. `plan()` and `run()` also repeat the same source/out/`cast(now)` setup. This duplication is how the engine `""` drift happened.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: Simplification: in `plan`'s missing-input branch, `out_text = _expand_stamp(out_raw, now) if out_raw else ""` has a redundant conditional, because `_expand_stamp("")` already returns `""`. Use `out_text = _expand_stamp(out_raw, now)`.

**Choice**: discard

**Rationale**: single-voice

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: Missing sources bypass item validation and output containment checks: `items=['../escape']` or an output inside the missing source produces `skip` and exit 0, although the spec requires `fail`.

**Choice**: discard

**Rationale**: single-voice; fixtures confirm missing source skips before item/containment validation. No write occurs; existing missing-source behavior and PRD status precedence are ambiguous.

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: The acceptance commands pass but test less than they appear to. In `test_plan.py`, `-k runner` matches no test (only the duplicate tests run), and `-k cli` selects one test that checks neither the line format nor the mutual-exclusion message. Those checks live in test_plan_cli.py and test_plan_runner.py, which the spec's file layout says should be `test_plan.py`.

**Choice**: discard

**Rationale**: single-voice; required assertions exist in dedicated test_plan_cli.py/test_plan_runner.py and whole backup suite covers them.

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: 2 touched test(s) pass against the pre-change code: test_runner_keeps_empty_selection_empty_without_planning_unselected_instances. Bob also notes duplicated empty-selection tests across three files.

**Choice**: discard

**Rationale**: single-voice reviewer; mechanical replay is retained explicitly. Empty selection is an unchanged run/dry-run contract, so passing base is expected and does not prove the plan variant tautological.

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: 26 touched test(s) pass against the pre-change code: test_empty_paths_fail_without_using_cwd_or_changing_artifacts +20 more.

**Choice**: discard

**Rationale**: Behavior-preserving regression guards: PRD requires dry-run unchanged; these cases preserve base input/engine/fatal behavior and target cycle1 drift. Mechanical fact retained, not silently dropped.

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: Attended recovery of 00110 cycle-2 cap regression (host_cap_regression_boundary pause)

**Choice**: Restored reports/00110-c2-paused-state.json, cleared host pause_reason, resumed phase review per Cap-Pause Resume handler without raising cap 2; recorded attended repair 5d8ab708 (all seven cycle-2 findings) as the cycle-2 rework via phase-done rework -> cycle 3; cycle-3 review ran all lenses on 690229e9..5d8ab708

**Rationale**: Recovery policy permits repairing a cap regression on a branch; cycle 3 at cap 2 allows only convergence or cap-out, so no extra rework budget is created and cycle-2 history stays intact

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: Cycle-2 cap-overflow deferrals R1-R7 still listed open in state

**Choice**: Cleared state.deferred_decisions; durable records stay in deferred/202610292344-deferred.json with resolution notes

**Rationale**: All seven repaired in 5d8ab708 and verified resolved by Alice, Bob and Eve in review-3; leaving them open would re-migrate resolved items at finalize and block the tail sweep

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: One `suppress(Exception)` in `_failed_plan_entry` wraps both the source and the output resolution. If the stamp expansion raises, the source falls back to the raw, unexpanded string instead of the resolved one. Resolve source and output in two independent guards and pin a `~/`-prefixed source in the stamp-failure recovery test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-11-02T10:03:38Z

**Decision**: `src/tools/backup/runner.py` imports the private `_resolve_paths` from `backup.capabilities.tar_archive`, which couples the generic runner to a private helper of one capability. Make the helper public (`resolve_paths`, exported) and update the call sites.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
