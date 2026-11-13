# Backlog review - gems - 2026-11-10

Verdict: NO-GO at review time (12 PRDs already implemented by hand); resolved by the apply pass below - backlog empty.

Scope: report-only. Ordering checks requested for 00124-00128; the rest got hygiene, grounding and an implemented-already pass.

## Ordering checks (requested)

| Check | Result |
|---|---|
| 00125 -> 00127 -> 00128 run in this order | Yes by number (autopilot drains ascending). Real dependencies agree: 00127 routes `--config` through `load_yaml`, which 00125 hardens (non-dict root); 00128 needs 00127's path to cover explicit files. Moot, see below. |
| 00124 runs first | Yes, lowest number. It is also the only PRD that may touch loader search path, so first is right. Moot, see below. |

## Blocking

- [00124, 00125, 00127, 00128] D Grounding: already implemented on this branch -> fails as: rework thrash / duplicate work (implementor finds nothing to change; regression tests "failing against current code first" cannot fail). Evidence:
  - 00124: `src/tools/braid/settings.py:13` `config_include_cwd: ClassVar[bool] = False`; resolver passes `include_cwd` (`resolver.py:310`); commit 0f8323e4 "exclude cwd from config discovery".
  - 00125: `click_integration.py:215,299-304` `config_error_exit_code`; `braid/cli.py:66` sets it to 2; `loader.py:27-28` raises `YAML root must be a mapping`; commit 70e30bac.
  - 00127: `resolver.py:226,234` explicit path goes through `load_yaml` + `merge_configs`; commit c386e7e4.
  - 00128: `resolver.py:230-233` unknown keys detected; commit 2d530277. Behavior differs from the PRD: it raises `ConfigurationError` (hard error), PRD asked for a warning. Decide whether the PRD or the code wins.
  Fix: move 00124, 00125, 00127 to done after one verification run of their repro cases; 00128 needs the warn-vs-error decision first.
- [00129-00135] D Grounding: commits 4cc38e2f, 00b5222d, 0c5741fc, 78652515, 290ada7f, 3af45c79, a91830c4 (all 2026-11-10, after the queue commit ec2d7ccf) match the titles of 00129/00130/00131/00132/00133/00134/00135. Not verified per PRD. 00126 matches e7d3f558 (warn about retired local override files). Fix: verify each repro, then move to done.
- [00133, 00134] Grounding: `ground_prd.py` reports `configuration.rst:316` and `zettel.rst:136` as missing (bare filename, no `docs/source/` prefix). Fix: use full repo-relative paths, or move to done with the others.

## Non-blocking

- Citation check: all dangling citations are in `research/`, `designs/`, `reviews/`, none under `backlog/` or `wip/`. No finding.
- 00127 and 00128 both say "failing against current code first"; true only if the fixes are reverted, so the regression-test wording is stale.

## Reshapes / Gaps

None. Sizes are 62-71 lines each, single template, one subsystem.

## End state

If the 12 PRDs are all confirmed implemented, the backlog is empty and the branch carries the whole agoge 2026-11-10 remediation. Open item: 00128 hard error vs warning, and whether braid.rst/configuration.rst document it.

## Decisions applied

- All 12 PRDs (00124-00135) moved to `prds/done/`. They were implemented by hand on this branch (no autopilot run, no review lenses). Verification instead: agoge run 2, `audit-results/agoge-2026-11-10-2.md`. It re-checked every prior finding against HEAD, fixed the residuals it found (00125 unreadable files, 00129 flag paths, 00131 symlink bypass, 00134 wrong `-f` flag in docs) and recorded deferred items there.
- 00128 warn-vs-error: the hard error stays. All four real tool configs on this machine pass it; CHANGELOG now marks it BREAKING under `### Changed` with the remedy.
- 00133/00134 grounding misses are moot (PRDs done).
- Backlog after apply: empty. Verdict: nothing left to run.
