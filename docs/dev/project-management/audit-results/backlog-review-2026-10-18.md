# Backlog review - buvis-gems - 2026-10-18

Verdict: GO (both PRDs READY; 0 Blocking open)

Reviewed commit: `e3498c4e`. Both backlog PRDs were read end to end before any finding was generated. All eight lenses ran inline (two PRDs, well under the delegation threshold). The "Decisions applied" section records the attended walk and the apply pass.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00098 | sysup-run-observability-v1 | standard | 185 | sysup runner, sudo capability, config, step_result, attention, CLI, new runlog; docs, changelog | none (builds on done 00092/00096) | READY |
| 00099 | dot-shared-config-host-fragments-v1 | standard | 181 | dot git service, new hostfilter, new share command, CLI; docs, README, changelog | none (builds on done 00090/00091/00095) | READY |

### Evidence and gate coverage

- Law: current `create-prd/SKILL.md` plus `minimal.md`, `standard.md`, `example_prd_rpg.md`; installed autopilot 0.9.0 `plan-tasks` steps 4-4.7 (150K per-task threshold, 55K overhead, `default_model` is a floor).
- Hygiene: two correctly named files in `backlog/`; `wip/` and `hold/` empty; `done/` holds 00088-00097. Numbers are unique across prds/ and intake/; 00098 and 00099 keep their intake item numbers as create-prd requires. No legacy `discovery/` directory exists; both source discovery docs live in `intake/processed/`.
- Citation resolution (`check_links.py --root . --json`): four rows under `prds/backlog/`, all on 00099 line 32, where `/Users/bob/x`, `/Users/bobby`, `/Users/bob.bak` and `/Users/bob-old` are regex boundary examples, not file citations. Waived as checker false positives (see N8). Zero rows under `prds/wip/`.
- Grounding resolution (`ground_prd.py --root . --json`): 0 blocking, 0 unverified. Every cited symbol resolved (`StepResult`, `SysupCommand`, `SudoPrime.prime`, `FatalError`, `Status`, `_RANK`, `_valid_entry`, `RED`, `Runner`, `fold_results`, `exit_code`, `DotGitService`, `read_manifest`, `atomic_write_bytes`, `atomic_write_text`, `CommandResult`); new symbols are declared.
- Manual `rg` grounding: every file in both Repository Structure trees exists except the files each PRD declares new (`runlog.py`, `test_runlog.py`, `hostfilter.py`, `share.py`, four dot test files). `console.status()` exists in the console adapter; `console.panic` exits 1; `BUVIS_AUTO_UPDATE=false` is honored because the update check instantiates `GlobalSettings` (prefix `BUVIS_`, field `auto_update`) and the updater returns early when it is false; `dot localize --to` exists, so the `--shared` with `--to` rejection is grounded; `save_divergence_patch` lives in `dot/divergence.py` and `apply_reverse_to_worktree` in the service, exactly as 00099 attributes them; `test_setup_real_git.py` already prefixes PATH with the interpreter bin. No `warned`, `runlog`, `hostfilter`, `dot-host`, `@HOME@` or `renormalize` exists in src or tests, so neither PRD is already implemented.
- Unattended feasibility: no human step in either PRD. Both run tests with mocked subprocesses or temporary bare repos. Warden `alwaysAllow` lists `python3` and `uv`, so the `python3 -c` and `uv run sphinx-build` acceptance clauses cannot hang the loop; `sphinx-build` acceptance also ran in done 00092/00093/00096.
- Budget sanity (bytes/4 + 55K): the largest 00098 task (CLI integration: `cli.py` about 9KB, `test_sysup_cli.py` 34KB, PRD slice about 19KB) lands near 75K; the largest 00099 task (service extension: `service.py` 30KB plus a new test file) near 70K. Both are far under 150K. 00099 deliberately adds new test files instead of editing the 94KB `test_git_service.py`.
- Known environment noise (project memory): three full-suite failures under the sandbox are env noise and the previous batch passed the same final gate, so no PRD change is needed for the `uv run pytest` exit criterion.

## Findings

### Blocking

None.

### Non-blocking

- [00098] B/C (wording): Feature "Selected-plan sudo prime" says the banner prints "immediately before validation". In `SudoPrime.prime` that means before spawning `sudo -v`, but `config.py` also has Pydantic validation, and the sentence does not say whether the banner precedes the `shutil.which("sudo")` check (a missing sudo would then banner and do nothing). Fix: say "after `sudo` resolves on PATH and immediately before spawning `sudo -v`".
- [00098] B (vacuous acceptance): the Phase 2 docs check asserts `"sudo"` and `"10"` in `docs/source/tools/sysup.rst`, and both already occur there (`order: 10` at line 43, `sudo-prime` at lines 67 and 105), so those two terms pass before any documentation is written. `"logs/"`, `"warned"`, `"Ctrl-D"`, `"Ctrl-C"`, `"error:"` are absent today and bind. Fix: assert `"sudo:"` and `"newest 10"` instead and ask the docs task to describe retention as keeping the newest 10 files.
- [00098] B/F (edits to existing tests): Phase 1 task 1 adapts the four existing prime tests in `test_runner.py` (they patch `sysup.runner.CAPABILITIES` with `MagicMock(spec=SudoPrime)` and will stop priming once priming is conditional). create-prd's model-tier guidance asks for an `rg -c` premise on such edits so a wrong turn cannot silently delete coverage. Fix: add a Premise line pinning the count (4) and requiring all four to be adapted, none deleted.
- [00098] H (creation-time decision): "exactly one final StepResult per steps-based entry, including with continue-on-error" goes beyond discovery R4b, which only redefined the all-exit-0 case. The decision is coherent (it makes warned/failed aggregation uniform), is announced in Success Metrics, and the task adds a Changed changelog entry. Recorded; no edit.
- [00098] A (cosmetic): Feature "Per-run log lifecycle" has two `- **Behavior**:` bullets. Coverage keys on `#### Feature:` headings, so nothing downstream breaks. Recorded; no edit.
- [00099] C (unnamed contract): the Git service module exports only `_ensure_filter_driver`, yet Phase 0 task 2's acceptance requires that "renormalize uses a shell-safe literal pathspec after `--`" and the share action "runs `cfg add --renormalize`" through the service. The method the share command calls is unnamed, so the planner or design would invent it. Fix: name `renormalize(path: str) -> CommandResult` in Exports and New symbols.
- [00099] B/F (late regression): Phase 0 task 2 adds a config read (and three writes when unset) to `DotGitService.__init__`, which every dot command and most dot tests construct. Existing constructor tests tolerate extra calls (fixtures reset the mock after construction, hooks-path tests filter by substring), but the task's acceptance runs only the new test file, so a regression would surface at the final `pytest -m dot` gate. Fix: also run `test_git_service.py`, `test_git_service_hooks_path.py` and `test_setup.py` in that task's acceptance.
- [00099] A/hygiene (N8): `check_links.py` reports four dangling citations on line 32; they are regex boundary examples (`/Users/bob/x`, `/Users/bobby`, `/Users/bob.bak`, `/Users/bob-old`), not citations. No implementor premise check reads them as paths. Waived here; no `link-ok:` token added because the line is a Contract that plan-tasks copies verbatim.
- [00099] H/B (standing-rule tension): R12's direct binary `sys.stdout`/`sys.stderr` writes in `dot filter` contradict the repo AGENTS.md Console methods rule ("No `print()`, `sys.stdout.write()`, `sys.stderr.write()`"). No ruff rule (no `T20` in `select`), hook, or invariant test enforces that sentence, and the PRD mandates a marker comment citing R12, so automated gates will not fight it; a doubt reviewer reading AGENTS.md might. Walked as a card: optionally extend the docs task with one AGENTS.md sentence naming the plumbing exception.

### Questions

- [00098] B/C: who renders mid-entry diagnostics. Feature "Progress and diagnostics" requires condensed exit-0 error lines and immediate failure diagnostics to print "before the next step starts" while each steps-based entry yields exactly one final `StepResult` and "diagnostics are not additional persisted results". Module: Execution owns progress and classification; Module: Attention and presentation says it renders "diagnostics/outcomes" from `cli.py`. The discovery is split the same way (status context in the runner per R1, Error lines printed by `cli.py` in its integration points). Only the runner knows the moment before the next spawn, so either `runner.py` prints through the console adapter (it already must import `console` for `console.status`), or it yields non-persisted diagnostic results the CLI must filter before `fold_results`. The PRD defers "internal capture-record shapes" to design but not this ownership. Recommended: pin runner-side rendering in Module: Execution and narrow the presentation module to yielded outcomes and the final log path.
- [00098] A: two `(guess)` contracts remain in "Per-run log lifecycle": same-second collision suffix `-1`, `-2` before the extension, and retention ordered by modification time with filename tie-breaker. Confirm and drop the markers so the task Contract carries no tentative wording.
- [00099] A: two `(guess)` contracts remain: a separate `CommandShare` class beside localize (the discovery leaned this way), and refusing `--shared` combined with `--to` before mutation. Confirm and drop the markers.

## Reshapes

- None. Both PRDs are under 200 lines, single-subsystem, three phases, six or seven tasks. 00098's discovery Q7 explicitly chose one PRD over a split sudo card. No cross-PRD dependency exists; 00098 (sysup) and 00099 (dot) share only `CHANGELOG.md`, appended sequentially under `[Unreleased]`.

## Gaps

- Traceability: 00098 carries discovery R1-R8 (R4b included) and all four discovery-review resolutions; nice-to-haves (step index in spinner, newest log in status) are excluded by name. 00099 carries R1-R13 and both open questions are resolved in the PRD; nice-to-haves (drift warning, `--unshare`) are excluded by name. No must-have dropped.
- Fix-type work ships its regression: the pre-existing `TimeoutExpired` escape (00098 R8) gets timeout tests in `test_runner.py` and `test_runlog.py`.
- Producer/consumer: 00099's `.gitattributes` is created by the share command; the per-host driver config is self-healed by the service; `dot` on PATH for git is an environment precondition the docs task documents. Nothing is consumed that nothing produces.
- Strategic: the deferred TUI diff-pane message issue from the previous review still has no PRD; carry it to the next `/assess-evolution`.

## End state after this batch

sysup runs become legible while they run: a status line per captured step, a framed and conditional sudo prime, exit-0 error lines surfaced live and folded into a new amber `warned` status, subprocess timeouts turned into failed results, and a per-run log under `$XDG_STATE_HOME/sysup/logs/` (newest 10 kept) that the summary names. dot gains a `dot-host` clean/smudge filter with one reserved `@HOME@` token, a per-host self-healed driver, and `dot localize --shared <path>` to opt a tracked file in without moving it, proven against real git on two hosts and against the divergence and reverse-hunk paths. Docs, README and changelog are updated by both PRDs. Still open: retaining raw `use:` capability output in the sysup log, an `--unshare` command for dot, and the TUI diff-pane message issue.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00098 | retain `default_model: opus`, `design: run` | invented error-scan predicate, interrupt-safe log and refresher lifecycle, equivalence with 00092 contracts; design must settle the capture-record shape and (if left open) diagnostic ownership |
| 00099 | retain `default_model: opus`, `design: run` | byte-identical round-trip obligation and a Git filter contract shared by checkout, pull and patch paths; design settles the private transform return shapes |

## Decisions applied

The four cards were walked in the attended session; the user took the recommended option on each. The five routine Non-blocking edits were applied under standing authorization and are listed here so nothing is silent. No PRD was reshaped, held or waived.

- D1 [00098] Runner renders mid-entry diagnostics: Module: Execution now owns every console status context and prints the immediate failure details, condensed exit-0 error lines and overflow line from src/tools/sysup/runner.py before the next step starts; Module: Attention and presentation renders only yielded outcomes and the final log path.
- D2 [00098] Both log guesses confirmed: the two `(guess)` markers on the collision suffix and the retention order were dropped; text unchanged.
- D3 [00099] Both share guesses confirmed: the two `(guess)` markers on the separate `CommandShare` class and the `--shared` with `--to` refusal were dropped; text unchanged.
- D4 [00099] Console-rule exception documented: `AGENTS.md` joined the Repository Structure and the Integration module Location; the Phase 2 docs task adds one sentence to the AGENTS.md Console methods list naming dot filter plumbing as the sanctioned exception (citing R12), with `rg -c "dot filter" AGENTS.md` printing 1 as acceptance (0 today, so the check binds).
- R1 [00098] Banner wording: "after sudo resolves on PATH and immediately before spawning sudo -v".
- R2 [00098] Docs acceptance: `"sudo"` and `"10"` replaced by `"sudo:"` and `"newest 10"` (both absent from `docs/source/tools/sysup.rst` today); the task asks for a `sudo: true` example line and the "newest 10" retention phrase.
- R3 [00098] Phase 1 task 1 premise: four prime tests building `MagicMock(spec=SudoPrime)` (count verified at 4 with `rg -c -F`), adapt all four, delete none.
- R4 [00099] Service method named: `renormalize` (root-relative path in, `CommandResult` out, literal pathspec after the double dash) in the Git service Exports and New symbols, referenced from the share feature.
- R5 [00099] Phase 0 task 2 acceptance also runs `test_git_service.py`, `test_git_service_hooks_path.py` and `test_setup.py` so the constructor change is checked in-task.

## Apply-pass validation

- Lens A rerun on both touched PRDs: every standard-template heading present in order; five unique features each; 7 of 7 and 6 of 6 task lines carry `Acceptance:`; frontmatter holds only `default_model` and `model_tier_rationale`; no `(guess)`, TBD, TODO or placeholder markers remain; 185 and 182 lines.
- Grounding resolution rerun: 0 blocking, 0 unverified, 16 declared-new rows (`renormalize` now among them).
- Citation resolution rerun: the same four waived regex-example rows on 00099 line 32; nothing new under backlog or wip.
- `git diff --check` clean. The review touched only the two PRDs and this report; no production code, tests, worktrees, branches or lifecycle moves.
- Gate honesty: all eight lenses ran inline; no subagent was used; no lens was skipped. The three known env-noise full-suite failures under the sandbox are an environment fact the previous batch already passed through, not a PRD defect.

The backlog is ready for `/autopilot:run-autopilot`. This gate did not execute PRD tasks and did not invoke review-work-completion.
