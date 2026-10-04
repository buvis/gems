# Backlog review - gems - 2026-07-10

Verdict: **GO.** All 9 Blocking findings resolved in the apply pass (2026-07-10); every PRD in `backlog/` is READY. The former launch precondition is satisfied: the seam spec `dev/local/specs/all-interface-architecture.md` was written and accepted attended the same day (seam = command classes via composition root, registry for name-based transports; `success=False → HTTP 422`). 00051's deliverable therefore exists — the PRD moved `hold/` → `done/`. The batch can launch with `/run-autopilot`.

Scope: 21 PRDs, `dev/local/prds/backlog/00041`–`00061`. Law: `create-prd` SKILL + assets as of today. Grounding: repo HEAD `fd48f36` (no commits since the PRDs were authored, 2026-07-09); all file/line claims verified by 7 parallel rg-based subagents. Machinery semantics verified against `run-autopilot` SKILL. Issues #92, #111–#114 confirmed open on GitHub.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00041 | atomic-write foundation | minimal | 47 | lib/filesystem, zettel, updater, bim doc | — (feeds 49, 56) | READY (fixed) |
| 00042 | bim serve confinement+auth | standard | 102 | bim serve + frontend | — | READY (fixed) |
| 00043 | bim doc promote collision | minimal | 41 | bim doc | — | READY |
| 00044 | bim doc claim/dedup | minimal | 48 | bim doc | — | READY (fixed) |
| 00045 | dot rm safety | minimal | 44 | dot | — | READY |
| 00046 | dot TUI secret status (#92) | minimal | 38 | dot | — | READY |
| 00047 | updater fail-loud | minimal | 39 | lib/updater | — | READY |
| 00048 | fctracker integrity | minimal | 40 | fctracker | — | READY |
| 00049 | pidash hook durability | minimal | 48 | pidash | 00041 | READY (fixed) |
| 00050 | zettel scanner errors | minimal | 40 | lib/zettel | — | READY |
| 00051 | all-interface seam design | minimal | 47 | spec doc | — (gates 53/54/57) | DONE (spec written attended 2026-07-10) |
| 00052 | decouple pybase from Click | minimal | 42 | lib/configuration, updater | — | READY |
| 00053 | dot git-ops unification | standard | 92 | dot | 00051 (implicit — fix) | READY (fixed) |
| 00054 | bim serve/TUI convergence | standard | 100 | bim serve, tui, frontend | 00051, (00042 same files) | READY (fixed) |
| 00055 | bim cli modularization | minimal | 44 | bim | soft: after 00054 | READY |
| 00056 | bim doc migrate-layout | minimal | 45 | bim doc | 00041 | READY |
| 00057 | bim doc triage review | minimal | 45 | bim doc + serve | 00051, 00043, 00044 | READY (fixed) |
| 00058 | dot diff-layout extraction | minimal | 42 | dot TUI | — | READY |
| 00059 | pidash state schema | minimal | 43 | pidash | — | READY (fixed) |
| 00060 | delete dead code | minimal | 47 | lib, tools, docs, packaging | — | READY (fixed) |
| 00061 | prune formatting | minimal | 42 | lib/formatting, bim | — | READY |

Hygiene: clean. Only `NNNNN-{slug}-v1.md` files in `backlog/`; sequence 00041–00061 unique and consecutive; no `wip/`/`stalled/`/`done/`/`discovery/` dirs exist yet, so no cross-dir collisions or overlaps. All 21 PRDs carry every template heading in order; every task line has an `Acceptance:` clause; no `{...}`/TBD stubs.

## Findings

### Blocking

1. **[00051] A/B — `design: skip` + `design_gate: user` is a silent no-op, and the in-task PAUSE has no mechanism.** run-autopilot fires the design gate only *after a successful design run*; with `design: skip` Phase 1.5 advances straight to planning, so the user review this PRD promises never happens. Task 2's "PAUSE for user review" executes inside `/work`, where loop mode explicitly bans mid-turn questions. → fails as: **unattended hang** (or silent skip of the gating review that 00053/00054/00057 depend on). Fix: `design: run` + keep `design_gate: user`; strip the in-task PAUSE (the Phase 1.5 gate is the review point).
2. **[00054] E — deletes the PATCH route body that 00042 just secured.** By execution time the PATCH handler carries 00042's `confine_path` + token check, and `api.ts` carries the token header; 00054's text ("delete the PATCH route body; delegate") never requires preserving them, so the blind (PRD-only) reviewer would pass a diff that drops the security layer. → fails as: **goal reversal** (security regression inside the same batch). Fix: preservation clauses + acceptance "out-of-vault/tokenless PATCH still 403/401"; Risk bullet naming 00042.
3. **[00053, 00054, 00057] B/E — dangling pointer to "the 00051 contract".** Tasks say "per the 00051 contract / seam" without naming `dev/local/specs/all-interface-architecture.md`; 00053 never references the spec at all despite 00051 declaring itself its gate. Test authors see task text only. → fails as: **wrong-TDD lock-in** (planner invents the result mapping). Fix: name the spec path in all three.
4. **[00057] B/C/D — conditional descope task is unexecutable, contradicts the Must-haves, and points at the wrong data.** Phase 0 task 1 says "check a week of `state_dir` triage data", but `state_dir` holds no triage data (state_db tables: processed/claims/originals/rule_matches; the queue is `<business_root>/_triage/*.proposed.yml`) — and the live config's `business_root` (`~/bim-doc-test/business`) no longer exists, so there is nothing to validate. If the descope branch fired anyway it would contradict the Must-have "registered in the serve action registry". "WebUI can list and approve" is also ambiguous (generic `POST /api/actions/{name}` vs. new Svelte UI — and the frontend has zero test infra). → fails as: **rework thrash** (reviewers hold the Must-haves against a descoped diff). Fix: drop the conditional task; commit to CLI + registry; acceptance via TestClient on the generic actions route; explicit "no new Svelte UI"; docs (bim.rst) to Must-have.
5. **[00042, 00054] B — WebUI acceptance criteria are not headlessly verifiable.** The SvelteKit frontend has no test infrastructure at all (no vitest/playwright/svelte-check; package.json scripts: dev/build/preview). "WebUI still works with the injected token" (00042) and "a forced failure shows an error in the WebUI" (00054) cannot be demonstrated by any in-repo command. → fails as: **rework thrash / false-done** (reviewer and implementor disagree on an uncheckable criterion). Fix: reword to backend-verifiable proxies (TestClient: served index.html carries the token; tokenless → 401; action route returns non-2xx + envelope; TUI failure via Textual test) and state that frontend changes are verified indirectly, manual smoke post-merge.
6. **[00059] B/D — snapshot acceptance can't be demonstrated on this machine, and one target surface is already covered.** Snapshot tests auto-skip off the canonical env (this is darwin); baselines are only produced by `gh workflow run update-snapshots.yml` (which commits to the repo). "A layout tweak requires a snapshot update" is undemonstrable in-session. Also the multi-session sidebar is *already* snapshotted (`test_multi_session_with_many_sessions`); the genuinely missing surfaces are the attention banner and dedicated pipeline/progress states. → fails as: **false-done / rework thrash**. Fix: retarget the surface list; acceptance = snapshots collected-and-skipped locally + baseline workflow step documented (triggered post-batch); the contract test is the in-session gate.
7. **[00044] D/B — premise partially wrong: `claimed_at` already exists.** `state_db.py:84` defines `claimed_at TEXT NOT NULL`, written at `:161-168`, never read. The Phase 0 task "Add a claimed-at timestamp + stale-claim predicate" would trip `/work`'s premise gate (a premise failure always stalls in loop mode). The max age is also unpinned ("e.g. matching a slow OCR ceiling"). → fails as: **stall** + wrong-TDD lock-in on the threshold. Fix: reword to "add a stale-claim predicate reading the existing `claimed_at` column"; pin `CLAIM_MAX_AGE_SECONDS = 3600` (user-confirmed value).
8. **[00041] C/D — success criterion unachievable at this PRD's completion + stale refs.** "Three of the four atomic-write copies are gone": the four are doc/shared (canonical), pipeline.py's os.replace placements, pidash session.py, pidash settings.py — 00041 removes only the doc-local copy; pidash's two are 00049's scope. Also `create_zettel_use_case.py:71` → the file is 35 lines (save at `:31`), and the acceptance `rg "doc/shared/atomic_write"` can't match dotted imports. → fails as: **rework thrash** (reviewer counts copies and fails the criterion). Fix: reword criterion (doc-local copy gone; lib canonical; pidash follows in 00049), fix the line ref, fix the rg acceptance.
9. **[00049] D — two premise errors.** (a) #114's "double render" does not reproduce: `console.report_result` never renders the hook rows (it prints `result.output` on success / delegates on failure), so rows render once per path — the real smell is the row-rendering loop duplicated between `_render_status_failure` and `hooks_status`. (b) cleanup-session does not write `state.json` (it writes only the per-session mirror); the actual state.json writers are update_tasks, sync_agent_return, set_attention, clear_attention. → fails as: **stall** (premise gate) / wasted hunt for a non-bug. Fix: correct the lock list to the four real writers; reframe #114 as "deduplicate the row-rendering helper; close #114 as not-reproducible".

### Non-blocking

- **[00052] D:** "14 `click.echo` sites" is stale — 9 exist (5 in `updater/__init__.py`, 4 in `executor.py`). Requirement is count-independent; fix the prose.
- **[00060] H:** CHANGELOG entry listed as Nice-to-have, but the global changelog rule makes it mandatory for a user-visible removal (hello-world console script) — the commit hook will enforce it anyway. Promote to Must-have.
- **[00042] B:** token header name + injection mechanism left open ("index.html or /api/session"). The design phase (design: run) will pin them; pinning now (`X-Buvis-Token`, injected into served index.html) saves a design decision. Optional.
- **[00049] G:** the live hooks under `~/.claude/hooks/` are installed *copies* — the fix reaches the running autopilot machinery only after a `pidash hooks install` re-run. Add a Nice-to-have note; also an operational note below.
- **Frontmatter tuning** (see table below): `design: skip` for 00046/00048/00060/00061.

### Questions

- **[00060] B/D:** "Confirm no out-of-repo consumer of the uv adapter" — an unattended session cannot decide this (the PRD itself marks it UNVERIFIED). Only the author knows whether any other repo imports `buvis.pybase.adapters.uv` from the published wheel. Resolve now; then the conditional leaves the PRD.

## Reshapes

- **Optional, not required:** merge 00045+00046 (two tiny dot git-secret fixes) to save one ceremony cycle. Recommendation: keep separate — independent test surfaces, cleaner review diffs; cut 00046's ceremony with `design: skip` instead.

## Gaps

- No producer/consumer holes: 00041 feeds 00049/00056; 00051 feeds 00053/00054/00057; all dependencies point at lower numbers (roadmap's check re-verified).
- Every fix-type PRD ships its regression test. No half-migrations: each pattern change migrates all its callers within the batch.
- Operational (not a PRD defect): bim doc's live config points at a deleted sandbox (`~/bim-doc-test`) — after 00056/00057 the tool still needs real config to be useful. And during THIS batch, the old unlocked pidash hooks keep writing state.json (00049's fix deploys only on reinstall).
- Strategic: the backlog is the complete 2026-07-09 roadmap; the "opportunistic" list is intentionally unqueued. No missing-enabler found.

## End state after this batch

All five AGENTS.md invariant GAPs close (atomic persistence 41+49, path confinement + auth 42, claim release 44, lib Click-free 52, one-action-one-implementation 51+53+54). The seam spec exists and three refactors consume it; dot has one git implementation; bim's CLI is a composition root; the doc workflow gains its two promised commands (migrate-layout, triage); ~1,650 LOC of dead weight is gone. Still open after the batch: WebUI parity beyond bim (explicit non-goal), no frontend test harness (accepted trade-off), one `update-snapshots` workflow run for new baselines, one `pidash hooks install` to deploy the hook fix.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00051 | `design: run` (was `skip`) + keep `design_gate: user` | the only mechanism that actually pauses for the seam review (finding 1) |
| 00046 | `design: skip` | mirror-one-guarded-call fix; the PRD is the design |
| 00048 | `design: skip` | two mechanical catches + one assertion, fully specified |
| 00060 | `design: skip` | deletions need no design doc |
| 00061 | `design: skip` | deletion + one file move, fully specified |

## Decisions applied

All applied 2026-07-10. Every touched PRD re-passed the lens-A structure check (headings intact, frontmatter well-formed, no dangling `00051` task references).

1. **00051 → HOLD** (`dev/local/prds/hold/00051-all-interface-seam-design-v1.md`). Reason: `design: skip` + `design_gate: user` was a silent no-op and the in-task PAUSE had no mechanism; the user chose to write the seam spec interactively before the batch. **Launch precondition:** `dev/local/specs/all-interface-architecture.md` exists before `/run-autopilot`.
2. **00054**: PATCH-delegation task now requires preserving 00042's `confine_path` + `X-Buvis-Token`; Phase 2 keeps the token header; new "00042 regression" Risk bullet; acceptance includes out-of-vault/tokenless PATCH → 403/401.
3. **00053/00054/00057** (and prose mentions in 00052/00056): every "per the 00051 contract/seam" replaced with the concrete path `dev/local/specs/all-interface-architecture.md`; 00053 gained a Design-input line in its Foundation layer.
4. **00057**: conditional validate/descope task deleted (the data it wanted doesn't exist — `state_dir` holds no triage data and the configured `business_root` is gone); full scope confirmed (CLI + registry via generic actions route, explicitly no new Svelte UI); `bim.rst` docs promoted to Must-have; list-task acceptance names the proposal fields.
5. **00042 + 00054**: WebUI acceptance rewritten to headless proxies (TestClient: served index.html carries the token; tokenless → 401; failing action → non-2xx envelope; TUI failure via Textual test); "frontend has no test harness, manual smoke post-merge" stated in Risks. Token pinned: `X-Buvis-Token`, injected into served `index.html`.
6. **00059**: surfaces retargeted to attention banner + dedicated pipeline/progress states (multi-session sidebar already snapshotted); acceptance = snapshots collected-and-skipped locally + `gh workflow run update-snapshots.yml` documented as the post-batch baseline step; contract test is the in-session gate.
7. **00044**: premise fixed — stale-claim predicate reads the *existing* `claimed_at` column (`state_db.py:84`, no schema change); max age left to the design phase with constraints (config-documented, must exceed a slow-ingest ceiling). User explicitly deferred the value.
8. **00041**: success criterion scoped to this PRD (doc-local copy gone; lib canonical; pidash handoff to 00049 explicit); `create_zettel_use_case.py:71` → `:31`; rg acceptance replaced with an import-source assertion.
9. **00049**: lock list corrected to the four real `state.json` writers (cleanup_session excluded, mirror-only); #114 reframed to "deduplicate the row-rendering helper; close as not-reproducible"; Nice-to-have notes the `~/.claude/hooks/` reinstall after merge.
10. **00045 + 00046**: kept separate (reshape declined); 00046 got `design: skip` instead.
11. **00060**: uv-adapter deletion made unconditional (user confirmed no out-of-repo consumers); CHANGELOG entry promoted to Must-have.
12. **Frontmatter**: `design: skip` added to 00046, 00048, 00060, 00061. **00052**: click.echo count corrected 14 → 9.

Final state: 20 PRDs in `backlog/`, all READY; 00051 in `done/` (its deliverable, the accepted seam spec, exists at `dev/local/specs/all-interface-architecture.md`). Verdict **GO** — nothing blocks `/run-autopilot`.
