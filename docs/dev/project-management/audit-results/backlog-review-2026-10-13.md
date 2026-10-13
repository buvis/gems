# Backlog review - buvis-gems - 2026-10-13

Verdict: GO (all 7 PRDs READY; 0 Blocking open)

Reviewed commit: `69371e2c`. All seven backlog PRDs were read end to end before findings were generated. The user accepted all six blocking fixes and the refresh-exit recommendation. The apply pass changed five PRDs (00092-00096); no production code, tests, or lifecycle locations changed. All eight lenses ran, and the edited PRDs passed the final compliance, citation, grounding and whitespace checks.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00090 | dot-host-links-localize-pull-rescue-v1 | standard | 265 | dot hostlinks, git, commands, CLI/TUI; console choose | 00088 (done) | READY |
| 00091 | dot-host-links-setup-v1 | standard | 190 | dot git, setup, status, settings, CLI | 00088 (done) | READY |
| 00092 | sysup-attention-layer-v1 | standard | 402 | sysup results, config, runner, attention, CLI; pybase ntfy | none | READY |
| 00093 | dot-add-untracked-files-v1 | standard | 329 | dot staging service, add command, tests | none; shares service with 00090/00091 | READY |
| 00094 | updater-installer-index-parity-v1 | standard | 209 | pybase updater lookup, cache, executor | none | READY |
| 00095 | dot-pull-divergence-report-v1 | standard | 278 | dot pull, git, status, CLI/TUI | 00088 (done), 00090 | READY |
| 00096 | sysup-expiry-registry-v1 | standard | 344 | sysup config, probes, runner, refresh, CLI; packaging | 00092 | READY |

### Evidence and gate coverage

- All lenses A-H ran inline. Seven PRDs do not meet the skill's approximately eight-PRD grounding-delegation threshold. No lens or dependency was skipped.
- Law: current `create-prd/SKILL.md`, `minimal.md`, `standard.md`, and `example_prd_rpg.md`; installed autopilot 0.9.0 `plan-tasks` steps 4-4.7. The task threshold is 150,000 tokens, distinct from the user's 500K session cap. `default_model` is a floor; `model_tier_rationale` is explicitly permitted by the current authoring skill, though ignored by the parser.
- Hygiene: seven correctly named files, unique PRD numbers; `wip/` and `hold/` empty; `done/` contains 00088. The legacy discovery directory is absent. All four actual discoveries live in `intake/processed/`; matching intake/PRD numbers reserve the same work identity under the current create-prd rule, not a collision. No ordering dependency points forward.
- `check_links.py --root . --json`: zero findings under backlog/wip, zero scan errors. Findings outside those directories are outside this review's gate.
- `ground_prd.py --root . --json docs/dev/project-management/prds/backlog docs/dev/project-management/prds/wip`: zero missing, unresolved, or unverified rows. Manual `rg` and source reads additionally checked the actual dot service/commands/hostlinks, sysup CLI/config/runner/capabilities, updater/cache/executor, tests, packaging, docs, history, and done trajectory. A declared-new symbol belonging to a prerequisite was checked against ordering, not treated as already implemented.
- Every standard-template heading is present in order, feature names are unique within each PRD, and all 46 tasks carry `Acceptance:`. No unresolved guess/TBD/TODO markers or implementation-time human approval requirement was found. Product prompts in dot and `sysup refresh` are exercised through mocks or temporary repos; they do not require a human during implementation.
- Observed test premises match: dot pull 6 functions, add 13, updater executor 20, sysup config 21, sysup CLI 15; dot's stage-interactive class has 10 functions / 13 parameterized cases. 00096 correctly anticipates the two config tests added by 00092. No premise was blindly replaced with a current suite total.
- Prior decisions in `backlog-review-2026-10-12.md` are preserved: no cosmetic cleanup of prerequisite New symbols lines, no forced split of localize/rescue, and no reopening accepted fetch-to-pull races, manual glean setup, or the deferred TUI pane problem.
- Public API checks used primary sources only. Current [mise latest documentation](https://mise.jdx.dev/cli/latest.html) describes release-age filtering and its setting/tool-option override, improving yesterday's unverified assessment; a real private mirror was not exercised. [GitHub CLI environment documentation](https://cli.github.com/manual/gh_help_environment) confirms the precedence issue in B2. No credential was read and no authenticated request was made.

## Findings

### Blocking — resolved

B1-B6 below preserve the original evidence and pre-edit locations. All six were resolved by the approved edits; none was waived.

1. **B1 [00095] D/H: text-mode capture corrupts a recovery patch.** Location: `00095-dot-pull-divergence-report-v1.md`, Success Metrics (line 31), Feature: Save patch (lines 54-66), Phase 2 real-git task. The PRD promises byte-for-byte recovery while routing the diff through `shell.exe` and `atomic_write_text`. `ShellAdapter.exe` uses `subprocess.run(text=True)` (`src/lib/buvis/pybase/adapters/shell/shell.py:58-63`), which normalizes line endings; the existing atomic writer also has a byte-writing sibling. An isolated real-git reproduction with `core.autocrlf=false`, CRLF base bytes, and a CRLF edit produced a raw patch passing `git apply --check` (exit 0), but the text-captured patch failed with `patch does not apply` (exit 1). Resetting after that save defeats discovery M3/M4. **Fails as: wrong-TDD lock-in** (LF-only and binary fixtures can pass while the promised recovery record is unusable). **Fix:** require byte-preserving diff capture and `atomic_write_bytes`, preserve the existing text adapter's semantics for other callers, and add a CRLF real-git roundtrip asserting exact recovered bytes before allowing resets; retain fail-closed handling for unsupported content.

2. **B2 [00096] D/H: the gh check can inspect the wrong credential.** Location: `00096-sysup-expiry-registry-v1.md`, Feature: gh-token-expiry (line 126), bundled gh-agent template, Feature: Run the refresh commands (line 177). Both child environments inherit `os.environ` and merely override `GH_CONFIG_DIR`. GitHub CLI documents that `GH_TOKEN` / `GITHUB_TOKEN` override stored credentials; `GH_HOST` can also select another host. Thus a healthy ambient token can mask the expiry or broken grant of the intended gh-agent token, and inherited authentication can interfere with renewal. This contradicts discovery B3's configured credential identity. **Fails as: wrong-TDD lock-in** (the specified env assertion passes without proving which credential is inspected). **Fix:** explicitly isolate gh probe and bundled gh-auth refresh environments from ambient token/host overrides, pin the supported GitHub host, and test with synthetic inherited overrides while asserting the parent environment is unchanged. No live token is required.

3. **B3 [00092] C/H: the specified nonfatal notifier can raise before its handler.** Location: `00092-sysup-attention-layer-v1.md`, Feature: pybase ntfy adapter (lines 179-188), Push once per ordinary run (line 203), CLI tail (lines 311-314). `build_ntfy_request(...)` is outside the supplied `try`, although `ValueError` is in the handler and notification failures must not raise or prevent persistence. A local stdlib check of `Request('not-a-url/topic', ...)` raises `ValueError` during construction without making a request. Following the pinned text loses the state-write step when the URL is malformed. **Fails as: wrong-TDD lock-in** (the supplied implementation and happy-path/HTTP-error tests agree while violating the failure contract). **Fix:** build the request inside the existing `try`; add a malformed-URL adapter regression and a CLI regression proving the warning, retained `notified: false`, state persistence, and unchanged run exit code.

4. **B4 [00094] C/G: the shared cache can reintroduce the PyPI/installer mismatch.** Location: `00094-updater-installer-index-parity-v1.md`, Feature: Checker uses the lookup (lines 46-51), Honest --update (lines 71-76), Phase 1 checker task. The PRD says the cache holds the installable version, keeps `fetch_latest_version` PyPI-only, and changes only the cache-miss call in `check_for_update`. Today `fetch_latest_version` writes the same `latest_version` / `last_check` fields (`checker.py:100`), and fresh-cache checks return before calling the new lookup (`checker.py:63-71`). Therefore `--update` can correctly report installer lag while caching the unavailable PyPI version for the next passive invocation; old PyPI cache entries have the same ambiguity. **Fails as: wrong-TDD lock-in** (isolated lookup tests miss the producer/consumer collision). **Fix:** separate or explicitly source-tag installer cache data, treat legacy untyped data as a miss for installer-aware checks, and prevent the informational PyPI query from populating the installer cache. Add the sequence regression: lag-reporting `--update`, then passive check, with zero installer upgrade or restart.

5. **B5 [00093] C: the mandated changelog text cannot pass its acceptance command.** Location: `00093-dot-add-untracked-files-v1.md`, Module: docs and changelog (line 265), Phase 0 implementation task (line 288). The exact bullet says `currently staged` in lowercase; the task requires case-sensitive `rg -c "Currently staged" CHANGELOG.md` to print 1. The required capitalization is absent from the supplied bullet. **Fails as: rework thrash** (verbatim text and verbatim acceptance disagree). **Fix:** make the check assert the exact lowercase phrase in the specified bullet without pinning a whole-file match count, or deliberately change the bullet to contain the quoted output label and align the check.

6. **B6 [00096] C/G: Phase 0 requires work assigned to later tasks.** Location: `00096-sysup-expiry-registry-v1.md`, Module: tests (line 263), Dependency Graph (lines 276-286), Phase 0 tasks (lines 295-296), Phase 1 runner task (line 304). The first independent Phase 0 task validates configured capabilities against a registry created by the second; more decisively, the second must pass `test_gh_token.py`, whose specified date-boundary test calls `classify_expiry`, introduced only in Phase 1 after Phase 0 passes. **Fails as: rework thrash** (the prescribed test cannot pass within its task's dependency closure; an implementer must pull later production work forward). **Fix:** order registry/probes before config validation, declare that dependency, keep Phase 0 probe tests about parsed outcomes, and move the classification-boundary assertion into the Phase 1 runner task. Alternatively combine the inseparable foundation work and explicitly move classification into that foundation.

### Non-blocking

- **N1 [00090, 00091, 00094, 00095] A/C: inherited structural detail gaps.** Locations: 00090 Modules and Apply rescue/pull features; 00091 Self-heal features and Modules; 00094 Repository Structure; 00095 Messages/Recovery output and Modules. Some feature fields and module responsibilities are omitted, some graph names identify subcomponents rather than literal Module headings, and some task-owned docs/tests are absent from the trees. Feature headings and acceptance clauses remain unambiguous; these are not a coverage-gate block. The same field omissions were explicitly retained yesterday. Do not reopen the cosmetic prerequisite-symbol decision.
- **N2 [00090] B/C: complete the plan record during design.** Location: Plan rescue line 74 versus dot pull with rescue lines 104-106. The listed `RescuePlan(moves, duplicates, collisions, skipped)` shape omits the `error` subsequently read and written by `CommandPull`. Specify an optional error field/default and the manifest parser's `(links, errors)` unpacking in the design contract. The intended fetch-error behavior is already stated, so this is a bounded refinement rather than an unresolved user requirement.
- **N3 [00093] C: “no git command” overstates missing-path behavior.** Locations: Success Metrics and final Critical Scenarios versus Module: dot.commands.add, which explicitly replaces code after the existing service-construction line. `CommandAdd.__init__` already constructs `DotGitService`, which checks/repairs the refspec; 00091 adds hooksPath checks. The actual new contract is no staging call for an absent path, which the named mock test checks. Align the prose to “no staging operation”; do not infer a new service-construction refactor.
- **N4 [00096] B/G: make optional-dependency tests independent of the optional dependency.** Locations: Success Metrics line 22 and Module: tests line 263. “Starts with pytest.importorskip” can be read as a module-level skip, suppressing the missing-extra and invalid-input tests along with certificate tests. Specify function/fixture-local skips for only the two certificate tests; the absence/error-contract tests must still collect and run without cryptography.
- **N5 [00092, 00096] B/F: repeated whole-tool gates.** Locations: 00092 Phase 1 Exit Criteria; 00096 Phase 0 and Phase 1 Exit Criteria. They run the entire sysup test directory before the final integration gate. Current create-prd's gate rule prefers task/phase-owned tests followed by the full gate once at the end. This adds avoidable work but does not make the batch unsafe.
- **N6 [00092, 00093, 00096] F: size is prose-heavy but not a demonstrated budget stall.** Locations: embedded final code and test tables under Functional/Structural Decomposition. These PRDs add roughly 8.3K/8.7K/9.2K tokens if copied whole. A conservative sample using all relevant existing files, the whole PRD twice (including a projected task body), and the installed 55K overhead yields about 75K/120K/79K respectively, below 150K before modest new-file growth. Trim repeated prose if desired; preserve contracts and the already chosen two-part sysup split. These are pre-apply review bounds, not an executed task plan; the accepted edits add bounded cache/credential/error cases within the same modules and do not require a reshape.

### Questions — resolved

- **Q1 [00096] B/C: amber refresh exit status.** Location: Success Metrics line 25 names `test_refresh_recheck_not_ok_keeps_entry_and_exits_1`; Feature: sysup refresh line 183 instead uses `exit_code(recheck)`, which returns 0 for `expiring`. Both retain the amber entry. Recommended resolution: explicitly keep `ok`/`expiring` exit 0 and `expired`/`unknown` exit 1, rename/parameterize the test to state that distinction. Alternative: make every non-ok refresh exit 1 while ordinary amber runs remain 0. The user selected the recommended mapping; the feature, named test, task acceptance, docs contract and critical scenario now agree.

## Reshapes

- None required. All cross-PRD dependencies are in ascending order; no PRD duplicates in-flight or completed work.
- Keep 00090 localize and rescue together as the discovery requires. Keep 00092/00096 as the two existing sysup delivery units. Correct B6 within 00096 rather than allocating another PRD.
- 00090/00091/00093/00095 share dot files but make compatible changes in different methods; 00095 already has `catchup: force`. 00092/00096 deliberately share the attention contract, and 00096 accounts for the changed CLI shape. Renumbering merely for adjacency would buy little and disrupt settled identities.

## Gaps

- B4's cache producer/consumer gap is closed by a separate installer record, legacy-cache misses and a same-state-directory sequence regression. B6's prerequisite gap is closed by registry-before-config ordering and Phase 1 classification tests.
- Discovery traceability: 00088 M8-M12 map to 00090/00091, with M13 still an explicitly attended post-shipping config step; 00089 M1-M9 map to 00095; 00093 R1-R8 map to its features/tests; sysup A1-A7 and B1-B6 map to 00092/00096. No new scope or dropped must-have was found. The missing-path change in 00093 is recorded as a creation-time decision and in commit `de5d49ab`, not an unresolved discovery question.
- All fix PRDs require regression tests. The missing cases above concern whether those tests establish the promised contracts, not an absence of testing.
- Still deferred from yesterday: TUI diff-pane messages overwritten on refresh, glean setup on this host, Windows junction settling, and optional unlocalize. No follow-up PRD exists for the TUI issue; retain it for the next `/assess-evolution` rather than expanding this batch.
- The capsule still describes 00092/00093 as intake-only-era context and records a dirty tree that is clean now. Catchup should refresh it; this review does not rewrite historical batch state.

## End state after this batch

With these approved specifications implemented, dot can localize and rescue host-specific files, bootstrap a new host, stage a new file reliably, and preserve conflicting edits in a recoverable divergence patch. The updater uses an installer-aware version source without treating informational PyPI data as installable. sysup gains persistent attention, nonfatal notifications, expiry probes tied to the intended credential, and an attended refresh command tested headlessly. The remaining manual gh-agent enablement and glean configuration are explicit product setup steps, not unattended build dependencies; the deferred TUI display issue remains.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00090, 00095 | retain opus and design | destructive file operations and recovery correctness |
| 00091 | retain sonnet and design | specified bootstrap commands; per-task classifier can raise a contract-edit task |
| 00092, 00096 | retain opus; no user design gate | shared schema, state/probe orchestration; implementation must stay unattended |
| 00093 | retain sonnet floor | exact implementation text; classifier may raise the exported return-contract task |
| 00094 | retain sonnet floor and design: skip | the edit fixes the separate cache record, source-selection API, legacy behavior and regression sequence; no interface choice remains for design, and the per-task classifier can still raise a contract-edit task |

## Decisions applied

All seven recommendations were accepted in the attended walkthrough. The full decision summary was printed before the batch edit. Non-blocking observations remain recorded; yesterday's explicit cosmetic decisions remain in force.

- B1 — applied to 00095: raw diff stdout, binary atomic persistence and a CRLF real-git recovery regression; binary capture uses the dotfiles root as cwd and leaves the shared text adapter unchanged.
- B2 — applied to 00096: gh probes and configured gh-login refresh steps remove ambient token/host overrides; both probes and bundled renewal pin github.com. Mocked regressions require the correct child config directory and unchanged parent environment.
- B3 — applied to 00092: request construction is inside the adapter's exception handler. Malformed-URL regressions require a warning, persisted unnotified state, no network call and unchanged exit code for both a failing run and a successful filtered run.
- B4 — applied to 00094: separate `installer_cache` record with method, timestamp and version; existing top-level fields stay PyPI-only. Legacy or mismatched-method data misses the installer cache. The real force/passive sequence shares a temporary state directory and must start no unavailable upgrade or restart. Its task explicitly depends on the passive-check integration task.
- B5 — applied to 00093: the acceptance command matches the exact lowercase phrase in the required Fixed bullet without a whole-file count.
- B6 — applied to 00096: registry/probes precede config validation with an explicit dependency; parsing tests remain in Phase 0, classification boundaries move beside the Phase 1 classifier. The config test-count assertion now correctly counts six additions in that file and one template test in its separate file (23 + 6 = 29).
- Q1 — applied to 00096: refresh exits 0 for ok/expiring and 1 for expired/unknown; all non-ok rechecks retain their entries. The regression name and parameterized expectations state that distinction.

## Apply-pass validation

- Lens A rerun on all five touched PRDs, with mechanical template checks across all seven: standard headings present/in order, unique feature names, accepted frontmatter, no unresolved stubs, all 46 tasks carrying Acceptance clauses.
- Citation resolution: zero backlog/wip findings and zero scan errors.
- Grounding resolution: zero missing/unresolved rows and zero unverified library rows. The five gh environment names are external CLI inputs, manually verified against the official manual and attributed on an explicit `link-ok:` line; they are not falsely declared as new Python symbols.
- Manual consistency review: new regression names appear in metrics/modules/tasks; changed dependencies close within their phases; the source-separated cache cannot be overwritten by the informational query; refresh retention and exit status agree with 00092.
- `git diff --check` passes. These checks validate specifications; implementation tests will run when the PRDs are executed.
- No reshapes, holds, waived blockers, or unresolved author questions. No worktrees, branches or temporary repo files were created by this review.

The backlog is ready for `/autopilot:run-autopilot`. This gate does not execute PRD tasks or invoke review-work-completion.
