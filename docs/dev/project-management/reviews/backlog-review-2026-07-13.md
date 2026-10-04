# Backlog review - gems - 2026-07-13 (attended re-review)

Verdict: **GO.** All 5 findings (1 Blocking + 4 Non-blocking) resolved interactively — the user chose the Recommended edit for each; all applied 2026-07-13/14 and lens-A re-verified. Nothing blocks `/run-autopilot`.

This attended pass supersedes today's earlier **unattended** review (run by `/brush` at 15:05, auto-applied 5 "Recommended" fixes, reported GO). It audited that run instead of trusting it: **4 of its 5 auto-edits verified correct; 1 verified factually wrong and reversed here** (finding 2 — the buvis-tracking claim in 00070 was "verified" with a vacuous command). It also re-ran all eight lenses with fresh eyes over the full 26-PRD backlog and found one new Blocking hazard the machinery-focused lenses had missed (finding 1).

Scope: 26 PRDs in `backlog/`. Law: `create-prd` SKILL + `assets/` (unchanged since 2026-07-10). HEAD: `b462a95`.

## Grounding method (why no per-PRD re-verification was needed)

`git diff --stat fd48f36..HEAD` shows the only changes since the 2026-07-10 review's verified baseline are: `.github/workflows/test.yml` (2 lines, pip-audit), `AGENTS.md`, `CHANGELOG.md`, `tests/tools/bim/doc/test_cli_audit.py`, `uv.lock`. **Zero `src/`, `docs/`, or `README` changes** — so the 07-10 subagent grounding of the 18 older PRDs and the 15:05 grounding of the 8 postup PRDs both remain valid against today's HEAD. Fresh spot-verification done this session:

- `dev/bin/scaffold.py --multi-interface` exists; generates `manifest.toml` + `adapters/cli.py`; entry module `{snake}.adapters.cli` — 00063's console script `postup.adapters.cli:cli` matches the scaffold exactly (the discovery doc's `postup.cli:cli` was the stale text; the PRD corrected it right).
- `hatch_build.py:79-92` `_build_frontend` is hardcoded to bim — 00067's added extension task correctly premised.
- test.yml has the per-tool change filter (`changed_tools`/`run_all`) — 00063's "CI path filter updated" is real; `BUVIS_SKIP_FRONTEND=1` in test CI confirmed.
- pidash `hooks/` contains exactly the six files 00069 names; `rg "flock|fcntl"` empty across pidash **with a positive control** (`rg "os.replace"` hits session.py + settings.py) — no lock primitive exists; 00069's "NEW with_state_lock" comment is correct.
- `~/.claude/skills/brief-portfolio/` exists with the exact shape discovery describes (collect.py/build.py/test_collect.py, 12-component Svelte SPA, derive.js + derive.test.js, template.html).
- bim serve has `_sse.py`, `frontend/`, `static/` — 00067's "mirror bim's `_sse.py`" is grounded.
- **npm in the unattended loop (00065-00067)**: `Bash(npm:*)`/`Bash(npx:*)` are allowlisted in `~/.claude/settings.json:80-82`, and warden's default rules contain no npm entries — `npm ci`/`run build`/`test` will not prompt mid-loop. Cleared.
- **CI launch precondition from the earlier report: RESOLVED.** `fc74a1e` (pip-audit `--skip-editable` + 8 dep patches) and `b462a95` (bim test Rich-wrap fix) landed after the unattended review; CI confirmed green (run 29255152474, per brush BR-3).

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00041 | atomic-write foundation | minimal | 47 | lib/filesystem, zettel, updater, bim doc | — (feeds 56, 63, 69) | READY |
| 00042 | bim serve confinement+auth | standard | 102 | bim serve + frontend | — | READY |
| 00043 | bim doc promote collision | minimal | 41 | bim doc | — | READY |
| 00044 | bim doc claim/dedup | minimal | 48 | bim doc | — | READY |
| 00045 | dot rm safety | minimal | 44 | dot | — | READY |
| 00046 | dot TUI secret status (#92) | minimal | 38 | dot | — | READY |
| 00047 | updater fail-loud | minimal | 39 | lib/updater | — | READY |
| 00048 | fctracker integrity | minimal | 40 | fctracker | — | READY |
| 00050 | zettel scanner errors | minimal | 40 | lib/zettel | — | READY |
| 00052 | decouple pybase from Click | minimal | 42 | lib/configuration, updater | — | READY |
| 00053 | dot git-ops unification | standard | 92 | dot | seam spec (done) | READY |
| 00054 | bim serve/TUI convergence | standard | 100 | bim serve, tui, frontend | seam spec, 00042 | READY |
| 00055 | bim cli modularization | minimal | 44 | bim | soft: after 00054 | READY |
| 00056 | bim doc migrate-layout | minimal | 45 | bim doc | 00041 | READY |
| 00057 | bim doc triage review | minimal | 45 | bim doc + serve | seam spec, 00043, 00044 | READY |
| 00058 | dot diff-layout extraction | minimal | 42 | dot TUI | — | READY |
| 00060 | delete dead code | minimal | 47 | lib, tools, docs, packaging | — | READY |
| 00061 | prune formatting | minimal | 42 | lib/formatting, bim | — | READY |
| 00063 | postup A: scaffold + collector | standard | 174 | postup (new) | 00041 | READY |
| 00064 | postup B: enrich | standard | 148 | postup | 00063 | READY |
| 00065 | postup C: web core | standard | 152 | postup | 00063, 00064 | READY (fixed: 3, 4) |
| 00066 | postup D: web views | standard | 158 | postup | 00065 | READY (via 00065's harness) |
| 00067 | postup E: serve | standard | 142 | postup | 00065, 00064 | READY (fixed: 5) |
| 00068 | postup F: TUI + brief | standard | 138 | postup | 00063, 00065 | READY (fixed: 4) |
| 00069 | postup G1: absorbed data layer | standard | 163 | postup (absorbs pidash hooks/state) | 00063, 00041 | READY |
| 00070 | postup G2: cycle views + cutover | standard | 150 | postup (retires pidash + skill) | 00064, 00067, 00068, 00069 | READY (fixed: 1, 2, 5) |

Context (not in backlog): 00051 in `done/` (seam spec accepted at `dev/local/specs/all-interface-architecture.md`, verified present); 00049/00059 in `hold/` (merge-absorbed into 00069/00070 — obligations re-traced this session: flock ✓, fsync #111 ✓, order #112 ✓, pass_context #113 ✓, render-dedup #114 ✓, versioned model + contract tests + snapshot gate + doc note ✓); 00062 discovery doc in `discovery/` (seeded the set, cross-referenced by all 8).

Hygiene: only `NNNNN-{slug}-v1.md` files in `backlog/`; sequence 00041-00070 consecutive and unique across backlog/hold/done/discovery; no `wip/` yet; all template headings present in order; every task line carries `Acceptance:`; no stubs/`(guess)`/TBD markers; all files under 200 lines.

## Findings

### Blocking

1. **[00070] B (self-referential hazard / loop self-harm)** — the pidash-retirement premise re-check reads as "run the real `postup hooks install` mid-loop". Task text: "re-check (cycle views on real portfolio + `postup hooks install` supersession) before removal"; feature text: "Re-check at execution: … `postup hooks install` supersedes pidash's entries". A literal work session would run the installer against the **live** `~/.claude/settings.json` + `~/.claude/hooks/` — replacing, mid-batch, the very hook machinery feeding the running autopilot's `state.json` (update_tasks/sync_agent_return/set_attention are live PostToolUse hooks). A bug in the freshly-ported hooks then corrupts state updates for the rest of the batch. Permission layers won't catch it (`uv run postup hooks install` is an innocuous-looking Bash line writing outside the repo via subprocess). 00069 itself is clean (all its install tests use fixture settings files; deployment is an explicit post-merge manual step) — only 00070's re-check wording invites the live run. → fails as: **loop self-harm**. Fix: pin the re-check to evidence that already exists headlessly — cycle views via TestClient over real state files + supersession via 00069's regression test suite — and state explicitly: do **not** run `postup hooks install` against the live `~/.claude` during the loop; deployment stays the documented post-merge step.

### Non-blocking

2. **[00070] D (grounding — reverses unattended auto-fix #4)** — the skill-deletion follow-up now claims `~/.claude/skills/brief-portfolio/` is "**untracked** by the buvis bare repo … a plain `rm -rf`, not a tracked-repo commit". **Wrong**: `git --git-dir=~/.buvis ls-tree -r HEAD` lists all 27 files of the skill as tracked. The unattended run verified with `ls-files`, which returns empty for *everything* against this bare repo (control: even tracked `.claude/AGENTS.md` comes back empty — empty index, so the check was vacuous; the classic empty-result-as-confirmation trap). The original discovery text ("buvis home repo — out-of-gems follow-up") was right all along. A user following the current instruction would `rm -rf` a tracked directory: status shows mass deletions, and a future machine re-provision resurrects the skill. Fix: correct the instruction to `git --git-dir=~/.buvis --work-tree=~ rm -r .claude/skills/brief-portfolio` + conventional commit + push.

3. **[00065, 00066] B/G (producer/consumer hole)** — acceptance criteria demand a ported derive test suite plus per-view component tests, but no task establishes a JS test runner, and the named exemplar (bim's frontend) has none: no vitest/playwright anywhere, and CI runs pytest only (`BUVIS_SKIP_FRONTEND=1`), so "gems gates green" never exercises JS tests. plan-tasks would have to invent the harness mid-PRD. Fix: name the runner (vitest — SvelteKit's default; the skill's existing `derive.test.js` ports to it trivially) in 00065's Phase 0 scaffold task, and add a Test Strategy line that JS tests run via `npm test` in-session/locally, outside the pytest CI gate. 00066 inherits the harness.

4. **[00065, 00068] C/E (understated blocked-by)** — 00065's Phase 0 generates fixtures "from the 00063/**00064** schemas" but its blocked-by names only 00063; 00068 tests "against the shared fixture payloads" (created in 00065) but blocks only on 00063. Ascending drain order satisfies both in the happy path; the headers exist precisely for the unhappy path (a mid-batch parking of 00064 or 00065 would let the dependent PRD start and fail/invent). Fix: add 00064 to 00065's blocked-by + dependency graph; add 00065 to 00068's. Zero practical cost.

5. **[00067, 00070] B (manual smoke inside Exit Criteria)** — 00067 Phase 2 Exit: "Success Metrics hold on the real portfolio (**manual smoke**: serve, browse, trigger collect, watch SSE refresh)"; 00070 Phase 1 Exit: "Cycle views render the real portfolio (**manual smoke**) and fixtures (CI)". Task-level acceptances are all headless (good), but a reviewer holding the phase exit against an unattended diff can't verify a manual smoke — same mechanism the 07-10 review fixed in 00042/00054 (its findings 5/6). Fix: reword both exits to the headless evidence (TestClient/SSE/trigger suites; aggregation over real state files) and move the browser smoke to an explicit post-merge note.

### Questions

None open. The npm-authorization question raised mid-review was resolved by evidence (allowlisted + no warden rule — see Grounding). The open design decisions inside the postup PRDs (model default, digest size, auto-collect-on-start, route pattern, state source paths) are all correctly routed to Phase 1.5 design (re-confirmed: no task acceptance depends on their outcome).

## Audit of the unattended run's 5 auto-edits

1. 00041 stale 00049 forward-ref → repointed at 00069 — **verified correct**.
2. 00067 hatch_build extension task added — **verified correct** (premise re-grounded at `hatch_build.py:79`).
3. 00069 `with_state_lock` net-new comment — **verified correct** (rg + positive control).
4. 00070 "brief-portfolio untracked, plain rm -rf" — **verified WRONG** (finding 2; evidence was vacuous).
5. 00070 CHANGELOG Added+Removed both required — **verified correct** (present in Success Metrics).

## Reshapes

None. 00049/00059 → `hold/` re-confirmed correct (same-file collision with 00069 otherwise; obligations fully traced). No merges/splits/renumbers warranted: all postup PRDs are 138-174 lines, single-subsystem, ≤3 phases; every cross-PRD dependency points at a lower number (full chain re-verified: 63←41; 64←63; 65←63(+64); 66←65; 67←65,64; 68←63(+65); 69←63,41; 70←64,67,68,69).

## Gaps

- No producer/consumer holes beyond finding 3 (JS test harness). hatch_build coverage for postup's frontend is already tasked (00067); publish.yml's node setup carries over unchanged.
- No half-migrations: pidash retirement and skill cutover are complete in-set with premise-gated deletions; dot git-ops unifies all three copies; formatting prune migrates its one consumer.
- Every fix-type PRD ships its regression test.
- Note (not a defect): 00056/00057 say "wire into `cli.py` per convention", which 00055 (runs first) obsoletes — post-split, new groups self-register. Self-corrects at execution (catchup + code reality); acceptance ("--help shows it") holds either way.
- Operational, outside PRD scope: 18 open renovate/dependabot PRs (oldest 2026-05-06). Not a launch blocker, but merging them mid-batch would churn `pyproject.toml`/`uv.lock` under PRDs that edit the same files — triage them before launch or freeze them until the batch lands.

## End state after this batch

All five AGENTS.md invariant GAPs close (atomic persistence 41+69, confinement+auth 42+67, claim release 44, lib Click-free 52, one-action-one-implementation 53/54/57 + postup by construction). postup ships as the repo's first all-four-interfaces gem; pidash and the brief-portfolio skill retire to exactly one portfolio implementation; the SvelteKit convention gains a second adopter; ~1,650 LOC dead weight gone; bim doc gains migrate-layout + triage; dot has one git implementation. Deliberate residuals: JS/Python derive dual implementation (fenced by shared fixtures), manual `postup hooks install` redeploy, buvis-tracked skill removal (finding 2's corrected instruction), one `update-snapshots` workflow run for new Textual baselines, deps-PR backlog.

## Frontmatter tuning

None new. 00046/00048/00060/00061 keep `design: skip`; 00053/00054 keep `design: run`; all postup PRDs correctly default to `design: run` (each is architecturally non-trivial) and `rework_cap: 3`.

## Decisions applied

All 5 findings walked interactively (attended); the user chose the Recommended option for each. Applied and lens-A re-verified (no heading/frontmatter/Acceptance-clause disturbed in any touched PRD):

1. **00070** (Blocking, finding 1): retirement premise re-check pinned to headless evidence in all three spots (Retirement feature Inputs, Phase 2 task, Test Strategy error case) — cycle views via TestClient over real state files + supersession via 00069's regression tests, with an explicit "do NOT run `postup hooks install` against the live `~/.claude` during the loop; deployment stays the documented post-merge step."
2. **00070** (finding 2): skill-deletion instruction corrected — `~/.claude/skills/brief-portfolio/` **is buvis-tracked** (ls-tree evidence, 27 files); removal is `git --git-dir=~/.buvis --work-tree=~ rm -r .claude/skills/brief-portfolio` + conventional commit + push. This **reverses the unattended run's auto-edit #4**, whose `ls-files` "verification" was vacuous (empty bare-repo index; control: tracked `.claude/AGENTS.md` also returned empty).
3. **00065** (finding 3): Phase 0 scaffold task now establishes a configured vitest runner (`npm test` green, empty suite ok); Test Strategy notes JS tests run via `npm test` in-session/locally, outside the pytest CI gate, and that 00066 inherits the harness.
4. **00065 + 00068** (finding 4): blocked-by headers extended (00065 += 00064 epics schema; 00068 += 00065 shared fixture payloads), mirrored in both Dependency Graph External lines. Execution order unchanged (ascending drain already satisfied both).
5. **00067 + 00070** (finding 5): both phase Exit Criteria reworded to headless evidence (TestClient/SSE/trigger suites; fixtures + real state files), with the browser smoke named as a documented post-merge step — matching the 00042/00054 precedent.

Skipped/deferred, named per fail-loud discipline: per-PRD lens-D subagent re-verification was replaced by the carryover proof in Grounding method (zero `src/`/docs changes since the verified baselines) plus fresh spot-checks of every load-bearing postup claim — nothing was accepted on the prior reports' word alone. The 18-open-dependency-PRs note (Gaps) remains an operational recommendation, not applied here (outside this skill's edit mandate). The `project-capsule.md` stale note flagged by the earlier report belongs to the capsule-refresh flow and was again left untouched.

Final state: 26 PRDs in `backlog/`, all READY. Verdict **GO** — `/run-autopilot` is clear to launch; the former CI precondition is already resolved (green run 29255152474).
