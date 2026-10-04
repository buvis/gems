# Backlog review - gems - 2026-08-07

Verdict: **GO** — all 5 Blocking findings resolved and applied (4 raised in the first pass, 1 caught by the post-apply verification sweep). 31 PRDs in `backlog/`, all READY. Nothing blocks `/run-autopilot`.

Initial verdict at report time was NO-GO (4 Blocking). The walkthrough ran attended; the user chose the Recommended option for every finding.

Scope: 32 PRDs in `dev/local/prds/backlog/` (`00041`-`00077`, 3,255 lines). Law: `create-prd` SKILL + `assets/` read at runtime today. HEAD: `5207640`.

Prior gate: `backlog-review-2026-07-13.md` cleared 26 PRDs (`00041`-`00070`) as **GO**. New since that gate and never reviewed: **00071, 00072, 00074, 00075, 00076, 00077**. This pass re-ran all eight lenses over the full set and found that a decision recorded in one of the new PRDs (00071) invalidates scope inside the already-cleared set (00069, 00070).

## Grounding method

`git diff --stat b462a95..HEAD -- src/ docs/source README.md` since the prior gate's verified baseline touches only: `morph` (new `pdf2png` command), `sysup` (mac/nvim/pip), `bim` frontend `package.json`/lock (renovate vite v8.2.0), `src/rust/Cargo.*`, `docs/source/tools/sysup.rst`. **Zero changes in the subsystems 00041-00068 target** (dot, bim doc/serve, fctracker, zettel, updater, formatting, lib/filesystem), so the 07-10 and 07-13 grounding of those PRDs carries to today. Fresh verification this session:

- `dev/bin/check_tool_wiring.py` exists (00074 cites it; AGENTS.md's `dev/bin` listing omits it, the file is real).
- `dev/bin/scaffold.py` emits `manifest.toml` with `[tool.interfaces]` - 00074's cli-only scaffold claim holds.
- CI coverage gates are real: `.github/workflows/test.yml:128` `--cov-fail-under=80` (lib), `:158` `--cov-fail-under=50` (per tool). All four klyreon PRDs' "≥50% tool coverage" is grounded.
- `console.confirm` (`console.py:156`) and `console.report_result` (`:242`) exist - 00076/00077 TTY offers and every klyreon `report_result` are grounded.
- `pybase.zettel` `_ZettelSafeLoader` exists (`.../file_parsers/parsers/markdown/helpers.py`) - 00074's sexagesimal-trap reuse claim holds.
- `pybase.filesystem.atomic_write` does **not** exist yet (positive control: `filesystem/__init__.py` exports `FileMetadataReader`) - 00041 is genuinely the blocker 00074 declares.
- Format spec sentence 00074 rewrites is real: `zettel-format-specification.md:118` "The internal format of MOC and trail files is deliberately not specified here yet".
- `claude --help` run this session: `-p/--print`, `--output-format json`, `--model` all exist exactly as 00075's adapter assumes. See finding N1 for what else it revealed.
- `~/.claude/skills/brief-portfolio/scripts/collect.py` still exists - 00070's parity-check target is grounded.
- **tracon is real and live**: `~/.claude/skills/run-autopilot/scripts/tracon/` (`discovery.py`, `model.py`, `panels.py`, `screens.py`, `stream.py` + 5 test modules) and `statectl.py`, self-described as an "atomic, advisory-locked JSON-state mutator". `~/.claude/hooks/` contains **no** pidash hook and `~/.claude/settings.json` contains no `pidash`/`update_tasks`/`set_attention`/`statectl` entry (positive control: `track_cost|PostToolUse` matches). This is the evidence behind finding B1.

Citation check (`scripts/check_links.py`): one hit under `backlog/` - 00076:41 `~/.claude/skills/klyreon/`, which is the install target the PRD itself creates. Forward reference, not a finding. All other dangling citations live in `project-capsule.md`, `specs/`, `notes/`, and the prior review file - out of scope for this gate.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00041 | atomic-write foundation | minimal | 47 | lib/filesystem, zettel, updater, bim doc | - (feeds 56, 63, 74) | FIX (N2) |
| 00042 | bim serve confinement+auth | standard | 102 | bim serve + frontend | - | READY |
| 00043 | bim doc promote collision | minimal | 41 | bim doc | - | READY |
| 00044 | bim doc claim/dedup | minimal | 48 | bim doc | - | READY |
| 00045 | dot rm safety | minimal | 44 | dot | - | READY |
| 00046 | dot TUI secret status (#92) | minimal | 42 | dot | - | READY |
| 00047 | updater fail-loud | minimal | 39 | lib/updater | - | READY |
| 00048 | fctracker integrity | minimal | 44 | fctracker | - | READY |
| 00050 | zettel scanner errors | minimal | 40 | lib/zettel | - | READY |
| 00052 | decouple pybase from Click | minimal | 42 | lib/configuration, updater | - | READY |
| 00053 | dot git-ops unification | standard | 92 | dot | seam spec (done) | READY |
| 00054 | bim serve/TUI convergence | standard | 101 | bim serve, tui, frontend | seam spec, 00042 | READY |
| 00055 | bim cli modularization | minimal | 44 | bim | soft: after 00054 | READY |
| 00056 | bim doc migrate-layout | minimal | 45 | bim doc | 00041 | READY |
| 00057 | bim doc triage review | minimal | 45 | bim doc + serve | seam spec, 00043, 00044 | READY |
| 00058 | dot diff-layout extraction | minimal | 42 | dot TUI | - | READY |
| 00060 | delete dead code | minimal | 52 | lib, tools, docs, packaging | - | READY |
| 00061 | prune formatting | minimal | 46 | lib/formatting, bim | - | READY |
| 00063 | postup A: scaffold + collector | standard | 173 | postup (new) | 00041 | READY |
| 00064 | postup B: enrich | standard | 147 | postup | 00063 | READY |
| 00065 | postup C: web core | standard | 153 | postup | 00063, 00064 | READY |
| 00066 | postup D: web views | standard | 157 | postup | 00065 | READY |
| 00067 | postup E: serve | standard | 142 | postup | 00065, 00064 | READY |
| 00068 | postup F: TUI + brief | standard | 137 | postup | 00063, 00065 | READY |
| ~~00069~~ | postup G1: absorbed data layer | standard | 163 | postup (pidash hooks/state) | - | **HELD** (B1) → `hold/` |
| 00070 | postup G2: brief-portfolio cutover | standard | 108 | postup (retires the skill) | 00064, 00067, 00068 | READY (rescoped, B1) |
| 00071 | retire pidash | minimal | 94 | pidash removal | - | READY (rewritten, B2) |
| 00072 | meta-budget share in postup | standard | 128 | postup | 00065, 00068 | READY (fixed: B5) |
| 00074 | klyreon A: core + vault | standard | 251 | klyreon (new) | 00041 | READY (oversize, N5) |
| 00075 | klyreon B: ingest | standard | 244 | klyreon | 00074 | READY (fixed: N1, N3) |
| 00076 | klyreon C: operator assets | standard | 192 | klyreon | 00074 | READY |
| 00077 | klyreon D: maintain + schedule | standard | 246 | klyreon | 00074, 00075, 00076 | READY (fixed: B3, B4) |

\* 00071 uses a non-template hybrid: `## Overview` / `### Problem Statement` / `### Success Metrics` then a bare `## Features` with a `#### Feature:` block and a `## Notes` section. It matches neither `minimal.md` (no Requirements/Implementation/Tasks/Success Criteria) nor `standard.md` (no Functional/Structural Decomposition, no Dependency Graph, no Implementation Phases, no task line, no `Acceptance:` clause). See B2.

Context (not in `backlog/`): `00051` in `done/`; `00049`/`00059` in `hold/`; `00062` and `00073` discovery docs. Sequence numbers unique across `backlog/`, `hold/`, `done/`, and `discovery/`. Only `NNNNN-{slug}-v{n}.md` files in `backlog/`.

## Findings

### Blocking

**B1. [00069, 00070] Lens E/H - tracon superseded the postup autopilot-dashboard scope (goal reversal).**
Location: 00069 whole PRD; 00070 "Capability: Portfolio cycle view" + Phase 0/1.

00069 ports pidash's six hook scripts into postup and ships `postup hooks install` to register them into live Claude Code settings, wrapping every state write in a new `with_state_lock` flock helper. 00070 then rebuilds pidash's dashboard as postup web + TUI cycle views. Both were written 2026-07-13/14. 00071, queued 2026-07-14 (later), records the opposite decision in plain text: "Successor: `tracon` (buvis home repo, `~/.claude/skills/run-autopilot/scripts/tracon/`)... tracon is presentation-only and out of gems scope", and states pidash is "already inert on the operator machine: hooks unregistered and deleted, `~/.pidash/` purged".

Evidence (verified this session, not taken from the PRD): `tracon/` exists with `discovery.py`, `model.py` (`LoopState`, `read_state`, `guards`, `build_steps_done`, `review_lenses`, `tasks_by_lane`, `prd_counts`), `panels.py`, `screens.py`, `stream.py` and 5 test modules. `statectl.py` describes itself as an "atomic, advisory-locked JSON-state mutator" - the durability guarantee 00069 proposes to build. `~/.claude/hooks/` contains no pidash hook and `~/.claude/settings.json` no pidash-related entry (positive control passed).

So 00069 would re-install a hook layer the operator deliberately removed, and re-implement locked atomic state writes that `statectl.py` already provides; 00070 would rebuild tracon's screens inside postup. **Fails as: goal reversal** - ~313 lines of PRD scope (two full autopilot cycles) rebuilding live buvis-repo machinery, ending with a repo the operator has already decided should not host it.

Not affected: postup's *portfolio brief* function (00063-00068, 00072) is a different surface from the autopilot cycle dashboard, and 00070's brief-portfolio parity check + skill cutover remain needed and grounded.

**B2. [00071 vs 00070] Lens E/A - duplicate pidash retirement with contradictory CHANGELOG obligations, on a non-template PRD.**
Location: 00070 Phase 2 task 1 + "Capability: pidash retirement"; 00071 "Feature: Remove tool, docs, packaging extra".

Both PRDs delete the same things: `src/tools/pidash/`, the console script, the `pidash` extra, `docs/source/tools/pidash.rst`, `tests/tools/pidash/`, the pytest marker, plus a CHANGELOG Removed entry. They name different successors in that entry: 00070 requires it to note "`postup` as the replacement" and a `postup hooks install` redeploy; 00071 requires it to name "`tracon` (buvis home repo) as successor". Ascending drain runs 00070 first, so 00071's premise re-check ("if already gone, skip and report") no-ops - after paying a full autopilot cycle (catchup, design, plan, work, review x N, blind, doubt) to do nothing. Both also claim to supersede `00049`/`00059`. Separately, 00071 matches neither template (see the Map footnote) and carries **no task line and no `Acceptance:` clause**, which `plan-tasks` copies verbatim. **Fails as: rework thrash** (contradictory CHANGELOG requirement between two PRDs in one batch) **plus wrong-TDD lock-in** (no acceptance clause - the planner invents one).

**B3. [00077] Lens G/H - MOC membership sync is a dropped discovery must-have.**
Location: discovery `00073-klyreon-cli.md` must-have "MOC authoring"; 00075:103; 00077 (absent).

Discovery requires: "MOC authoring: ingest creates a missing MOC file when it anchors to one, **and maintain keeps MOC membership in sync**". 00075 builds the ingest half and explicitly hands off the other half - line 103 ends "PRD D keeps membership in sync." 00077 never picks it up: its only MOC mention is removal during a prune (`prune.py`, "MOC member removal"). No feature, no module, no task, no acceptance criterion covers reconciling MOC membership with the zettels' `mocs` fields. **Fails as: dropped must-have** - after a zettel's anchors change or a zettel is edited by hand, its MOC listing drifts permanently and nothing reconciles it; the producer/consumer hole is invisible because both PRDs individually look complete.

**B4. [00077] Lens B - Phase 2 exit criterion is not verifiable headlessly.**
Location: 00077 Phase 2 "Exit Criteria": "Discovery success criteria 3 and 4 hold; the loop runs unattended end to end."

Discovery criterion 4 reads "a cron-driven run of **at least 7 days** over a mixed corpus". 00077's own Success Metrics correctly restate it in a fixture-checkable form ("a scheduled run over a mixed corpus completes with zero human input... `status` shows both mean links per zettel and the `literature`+`evergreen` count higher at the end than at the start"), but the exit criterion points back at the discovery text rather than at that restatement. A reviewer holding the exit criterion against an unattended diff cannot verify a 7-day soak and cannot make one happen. **Fails as: rework thrash** - same mechanism the 07-13 gate fixed in 00067/00070 (its finding 5) and the 07-10 gate fixed in 00042/00054.

**B5. [00072] Lens A - template stub left in Phase 2.**
Location: 00072 Phase 2 "Tasks".

*Found during the post-apply verification sweep, not the first comprehension pass - recorded here rather than quietly fixed.* The sweep compared, per PRD, the count of `- [ ]` task lines against the count carrying an `Acceptance:` clause. Every PRD matched except 00072, which had three task lines and two acceptances. The third was a literal placeholder:

```
**Tasks**:
- [ ] none
```

00072 was created 2026-07-14 19:09, after the 07-13 gate closed, so it had never been reviewed. **Fails as: wrong-TDD lock-in** - `plan-tasks` reads task lines and copies the acceptance verbatim; a task whose text is "none" and which carries no acceptance clause gets one invented for it. Fixed under the standing lens-A rule ("no template stubs left") rather than raised as a question: the Phase 2 heading is kept for template parity, the fake task line is gone.

*Method note (fail-loud): the same sweep's single-line regex under-counted 00072's two real acceptances too, because they wrap onto the following line. Verified by reading the file; no other PRD was affected, and the mismatch is what surfaced the stub.*

### Non-blocking

**N1. [00075] Lens D/B - the `(guess)` on the claude adapter resolves, and the CLI offers a stronger contract than the PRD assumes.**
Location: 00075:43 "Feature: Claude adapter".

Verified against `claude --help` this session: `-p/--print`, `--output-format json`, and `--model` all exist and behave as the PRD describes, so the marked guess is confirmed correct and can be pinned now instead of at implementation time. Two things the PRD did not account for: (a) `--json-schema <schema>` ("JSON Schema for structured output validation") makes 00075's fallback - "if the envelope does not parse, fall back to treating stdout as raw text and extracting the first fenced ```json block" - unnecessary hand-rolled parsing, when the payload schema is already a pydantic model the PRD defines; (b) `--tools ""` would *enforce* the PRD's own "text-in, JSON-out, no filesystem access to the vault" contract, which today rests only on setting `cwd` to a temp directory.

**N2. [00041] Lens C - internal contradiction on who repoints pidash's atomic-write copies.**
Location: 00041:9 vs 00041:47.

Line 9: "(pidash's copies are repointed in PRD 00049.)" Line 47: "pidash's two copies are repointed in 00069, which absorbed 00049's scope after 00049 was parked to `hold/` on 2026-07-13". The 07-13 fix landed on line 47 only. 00049 is in `hold/`, which autopilot never reads. Compounded by B1/B2: if pidash is deleted rather than absorbed, neither line is correct - the copies go away with the tool.

**N3. [00075] Lens E - dead exemplar pointer.**
Location: 00075:103.

Cites "pidash's marked-region pattern" as the model for the `<!-- klyreon:members -->` block, but 00070/00071 (both lower-numbered) delete pidash before 00075 runs. The delimiters and the rewrite-only-the-block rule are fully specified in place, so this is a dead pointer, not a missing contract. `src/tools/pidash/commands/hooks/install.py` is the real precedent today (the discovery doc cites it correctly at line 61).

**N4. [00074, 00076, 00077] Lens A - frontmatter asymmetry across the klyreon set.**
00075 carries `design_gate: user` and `rework_cap: 3`. 00074, 00076, and 00077 carry no frontmatter, so they take `rework_cap: 2` (the default lowered 2026-08-01). 00074 is the 246-line foundation the other three all depend on; a wrong contract there propagates through the whole set, and it is the one most likely to want a design gate and an extra rework cycle.

**N5. [00074, 00075, 00077] Lens A/F - three PRDs over create-prd's ~200-line split threshold.**
246, 244, and 224 lines against a "~200 lines -> split" rule. Flagged, not enforced: each is single-tool, exactly three phases, with contract-dense prose rather than padding, and the per-task PRD prose tax (~3K tokens against a 150K budget) is not what would stall these. Named here so the threshold breach is a recorded decision rather than an oversight.

### Questions

None open. Every ambiguity found either resolved against the repo (see Grounding method) or became a finding above.

## Reshapes

Both applied:

1. **00069 + 00070 (B1)** - **done.** 00069 parked in `hold/`; 00070 rescoped to the brief-portfolio cutover and renamed `00070-postup-brief-portfolio-cutover-v1.md`. The autopilot data-layer and cycle-view scope stays out of gems, where tracon and `statectl.py` already own it.
2. **00070 + 00071 (B2)** - **done.** The duplicate collapsed by construction: 00070 no longer touches pidash, so 00071 is the single owner with a single CHANGELOG obligation naming a single successor (tracon). 00071 rebuilt on `minimal.md`.

Number kept on both (00070 keeps its slot after the rescope; 00069's number stays with the parked file). No renumbering needed anywhere: every remaining cross-PRD dependency points at a lower number.

No renumbering needed on the klyreon set: every cross-PRD dependency already points at a lower number (74<-41; 75<-74; 76<-74; 77<-74,75,76; 72<-65,68).

## Gaps

- **RESOLVED 2026-08-09** (follow-up session; this was the one item the gate left open). The 00049/00059 obligations were traced against the buvis repo rather than accepted on 00071's word. Result, three ways:
  - **00049's lost-update class - covered.** `cli/state.py:128,185` takes `fcntl.flock(..., LOCK_EX)` on `<path>.lock` held for the whole body, read included. That is exactly the `with_state_lock` full read-modify-write serialization 00049 specified.
  - **00059's schema-drift class - covered, beyond what 00059 asked for.** `cli/schema.py` carries `SCHEMA_VERSION = 1`, `validate()`, `validate_changed()`, and a classifier separating unstamped / current / old / future / invalid (`:151-163`) - i.e. "an unknown version is handled with a clear message, never a silent misparse". Backed by `golden/state-*.json` fixtures plus `test_golden_contracts.py::test_golden_state_accepted_by_statectl_and_resume_target` (the contract test 00059 wanted) and enforced by `validate_state_json_hook.py`. The root cause - reader and writer in separate repos - is structurally gone now that reader, writer, and schema share one repo.
  - **00059's snapshot layout gate - obsolete.** It existed because pidash's layout was verified by eyeballing a live TUI (the 19-fix chain). tracon instead asserts directly on rendered structure across ~130 tests (`test_row1_renders_em_dash_for_unknown_task_and_cycle_counts`, `test_header_rows_are_no_wrap_with_ellipsis_overflow`). Different technique, binds to intent better than an SVG baseline; the premise is gone.
  - **One real survivor, now fixed.** `cli/state.py`'s three write paths (`atomic_write`, `_atomic_write_bytes`, `init`) published a temp file via `os.replace`/`os.link` with **no fsync** - #111's exact gap, relocated, and contradicting this repo's own atomic-persistence invariant. Fixed in buvis/home@29085d4d with an ordering regression test verified failing against the pre-fix code. #111 closed as fixed-elsewhere; #112/#113/#114 closed as superseded (all three are pidash-code-specific and die with the tool; #114 was already established not-reproducible in the 07-10 review).
- Klyreon set otherwise closes cleanly: every discovery must-have maps to a PRD except B3's MOC sync. `status`'s "promotion count" is a deliberate, documented substitution (00074 uses `evergreen`+`literature` counts as the proxy), not a drop.
- No half-migrations in the klyreon set: the spec engine has one implementation, `validate_vault` is reused by `maintain` rather than reimplemented, and the manifest is shared by 00076 assets and 00077 schedule.
- Every fix-type PRD in the set still ships its regression test.
- Operational, outside PRD scope: the dependency-PR backlog noted by the 07-13 gate. **Triaged 2026-08-09** ahead of the batch, 12 open PRs:
  - **Merged**: #137 (serde 1.0.229), #136 (regex 1.13.1) - Cargo.lock only, full matrix green, no batch contention. Master is green at `0b09bdf`.
  - **Auto-merged itself**: #144. Renovate had enabled auto-merge on 2026-08-06; the two merges above rebased it into a green state and GitHub merged it at 09:22 without anyone asking. **"Freezing" a renovate PR by simply not merging it does not work.** The freeze only holds after `gh pr merge <n> --disable-auto`, which was then applied to #140 and #117 (the only other armed PRs); all open PRs are now disarmed. Anyone re-triaging this backlog must check `autoMergeRequest` before assuming a PR is parked.
  - **Closed by dependabot itself**: #121, when asked to rebase. Not merged - `deploy-docs.yml` still pins `peaceiris/actions-gh-pages@84c30a85` (v4), so the 4.1.0 bump did not land and will presumably be re-proposed.
  - **Frozen, contends with the batch** (touches `pyproject.toml`/`uv.lock`, which 00041 and all four klyreon PRDs edit): #104 mypy v2, #103 ocrmypdf v17, #115 mypy range->`<3`, #116 ocrmypdf range->`<18`, #140 lock maintenance. Note #104/#115 and #103/#116 are duplicate pairs - renovate bumps the pin, dependabot widens the range, for the same two upgrades. Merging both of a pair conflicts. mypy v2 is the one to hold hardest: every klyreon PRD gates on `mypy strict` green.
  - **Frozen, needs code work**: #120 serde_yml 0.0.13 is a **breaking** change despite the 0.0.x patch-looking version - it fails to compile `zettel-core` with 5 errors (Mapping keys `Value`->`String` at `back_matter.rs:97`, `front_matter.rs:69`, `types.rs:126`; `as_f64()` no longer `Option` at `types.rs:84`; `TaggedValue.value` now private at `types.rs:134`). Recorded on the PR.
  - **Frozen, major or contending**: #117 (rust + bim frontend; last CI failed; auto-merge disarmed), #131 (typescript v7 - major, against the bim frontend that 00042/00054 rework).
  - Side effect worth knowing: merging into master makes renovate rebase its open PRs, each launching a ~140-job matrix that queues ahead of master's own run. Expect a CI backlog for a while after any merge.

## End state after this batch

With the klyreon set landed, gems gains tool 17: a Memex-Zettelkasten that ingests a dropped source into claim-bearing, contradiction-checked zettels and maintains itself from cron, with no human in the loop and no new dependency on the core install. All five AGENTS.md invariant GAPs still close (atomic persistence 41, confinement+auth 42, claim release 44, lib Click-free 52, one-action-one-implementation 53/54/57 + postup by construction). postup ships as the repo's first all-four-interfaces gem and absorbs the portfolio brief; the brief-portfolio skill retires.

What the batch leaves half-finished depends on B1's resolution. As written today it leaves gems hosting a second autopilot dashboard that the operator has already replaced with tracon, and pidash deleted twice with two different successors named in the CHANGELOG. With B1 and B2 resolved, the autopilot-monitoring surface lives in exactly one place (the buvis repo) and gems keeps only what it should: the portfolio brief, and now klyreon.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00074 | `design_gate: user`, `rework_cap: 3` | 246-line foundation; 00075/00076/00077 all consume its contracts. A wrong exported signature here propagates through three PRDs. Matches what 00075 already sets. |
| 00077 | `rework_cap: 3` | Largest rule surface in the set (promotion, assent, prune, two scheduler platforms) and the one PRD whose exit criteria reach outside the repo. |
| 00071 | moot if B2 merges it | Otherwise `catchup: skip`, `design: skip` - pure deletion. |

## Decisions applied

All findings walked attended; the user chose the Recommended option for every one. Applied 2026-08-07 and lens-A re-verified on every touched file (headings, frontmatter, `Acceptance:` clauses, `#### Feature:` uniqueness all re-checked).

1. **B1 - 00069 → `hold/`, 00070 rescoped.** `00069-postup-autopilot-data-layer-v1.md` moved to `dev/local/prds/hold/` (reason recorded here, not in the PRD). `00070` rewritten as `00070-postup-brief-portfolio-cutover-v1.md`: the Portfolio cycle view capability, its three features, and the pidash-retirement capability are gone; the data-level parity check and skill-deletion follow-up survive intact, including the 07-13 correction that `~/.claude/skills/brief-portfolio/` is buvis-**tracked** (`git rm`, never `rm -rf`). Blocked-by drops 00069 → now 00064, 00067, 00068. A rescope banner records why.
2. **B2 - 00071 rewritten on `minimal.md`.** Now template-compliant with four Phase 0 tasks, each carrying its own `Acceptance:` clause covering a distinct removal surface (package + tests; console script + wheel entry + extra + `all` + pytest marker; docs page + toctree; CHANGELOG). Sole owner of pidash removal, names `tracon` as successor, keeps the skip-and-report premise re-check. Frontmatter `catchup: skip`, `design: skip` (pure deletion).
3. **B3 - MOC membership sync added to 00077.** New `#### Feature: MOC membership sync`, new `klyreon.maintain.moc_sync` module block (`plan_moc_sync` / `apply_moc_sync`), a Phase 1 task with acceptance, dependency-graph entries in the Core and Integration layers, a Success Metric, a Test Strategy edge case, and the sweep order updated to `lint → transitions → MOC sync → prune → trail`. Rule fixed as deterministic (add zettels that anchor here, remove members that no longer do or no longer exist; never author a missing MOC - that stays ingest's job and a lint finding).
4. **B4 - 00077 Phase 2 exit criterion reworded.** Now points at the PRD's own headless Success Metrics including the criterion-4 stand-in, and names the literal 7-day live cron soak as a documented post-merge step that is explicitly not a gate on this PRD. Matches the 00042/00054/00067 precedent.
5. **B5 - 00072 stub removed.** `- [ ] none` replaced with a prose "none - completes in two phases" line; the Phase 2 heading stays for template parity.
6. **N1 - 00075 claude adapter pinned and simplified.** Flags verified against `claude --help` on 2026-08-07: `-p/--print`, `--output-format json`, `--model` all confirmed. Invocation now pinned as `claude -p --output-format json --json-schema <IngestPayload schema> --tools ""`. The hand-rolled fenced-```json-block fallback is gone: `--json-schema` moves shape enforcement into the CLI and a non-conforming response is a clean `BackendError(reason="schema")` rather than a salvage attempt. `--tools ""` now actually enforces the no-filesystem-access half of the backend contract that previously rested only on a temp `cwd`. Phase 1 task acceptance and the drift risk updated to match; the `(guess)` marker is retired.
7. **N2 - 00041 lines 9 and 47 corrected.** Both now say pidash's two atomic-write copies need no repoint because 00071 deletes the tool; 00049/00059 noted as staying parked.
8. **N3 - 00075's dead pidash pointer dropped** (line 103), and the handoff sentence repointed at 00077 by number now that the feature exists there.
9. **N4 - frontmatter.** 00074 gains `design_gate: user` + `rework_cap: 3` (246-line foundation consumed by three PRDs); 00077 gains `rework_cap: 3` (largest rule surface in the set).
10. **N5 - no edit.** The 200-line breach on 00074/00075/00077 stands as a recorded, deliberate decision.

**Collateral fixed (caused by the rescope, not pre-existing):** 00067 and 00068's Target Users lines referenced "PRD 00070's web cycle view" / "TUI cycle view", which the rescope deleted; both repointed at the cutover. 00063's "seven follow-on postup PRDs (00064–00070)" corrected to "(00064–00068, 00070, 00072)".

**Verified after the apply pass:** citation check re-run - the only hit under `backlog/` remains 00076:41's own install target (waived forward reference), no new dangling citations. Task-line/acceptance counts now match in all 31 PRDs. No `(guess)`, `TBD`, `TODO`, `???`, or `{...}` markers anywhere in `backlog/` (positive control passed). `#### Feature:` headings unique within 00070 and 00077. Sequence numbers unique across `backlog/`, `hold/`, `done/`, `discovery/`; only `NNNNN-{slug}-v{n}.md` files in `backlog/`.

**Skipped, named per fail-loud discipline:** per-PRD lens-D subagent dispatch (the skill's scale note for >8 PRDs) was **not** used - this session runs under a standing "no Agent tool unless requested" constraint. Lens D ran inline instead: the 26 previously-cleared PRDs rest on the carryover proof in Grounding method (zero `src/` changes in their subsystems since the verified baseline, shown by `git diff --stat`), and every load-bearing claim in the six new PRDs was verified directly this session with the commands recorded there. Two searches in that sweep initially returned empty for the wrong reason - `rg -r` (replace, not recursive) and a `*klyreon*` glob that cannot cross `/` - and both were re-run with positive controls before any conclusion was drawn; the coverage gate and the klyreon docs both exist. `project-capsule.md`'s stale entries (5 dangling citations) again belong to the capsule-refresh flow and were left untouched. The open dependency-PR triage remains an operational recommendation, outside this skill's edit mandate.

Final state: **31 PRDs in `backlog/`, all READY. Verdict GO.**
