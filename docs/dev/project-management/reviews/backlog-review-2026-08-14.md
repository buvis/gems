# Backlog review - gems - 2026-08-14

Verdict: **GO** — the one Blocking finding (F1, 00066) was raised, decided attended, and applied; all 31 PRDs in `backlog/` are READY. Initial verdict at report time was NO-GO (1 Blocking).

Scope: re-review of the same 31 PRDs the 2026-08-07 gate cleared GO (`00041`–`00077`, 3,306 lines). No PRD file changed since that gate's apply pass (newest mtime 2026-08-07 11:49). Law: `create-prd` SKILL + `assets/` re-read today. HEAD: `1d1df9b`. Prior decisions from the 08-07 walkthrough treated as settled; this pass re-ran all eight lenses looking for what changed and what both prior gates missed.

## Grounding method

Carryover chain, each link verified this session:

- 07-10 gate verified 00041–00061 at `fd48f36`; 07-13 at `b462a95`; 08-07 at `5207640` with follow-ups through `0b09bdf` (2026-08-09, master green).
- `git diff --stat 5207640..0b09bdf -- src/lib src/tools tests docs`: only the bim frontend `package-lock.json`. `git diff --stat 0b09bdf..HEAD`: only workflows (setup-uv v10), `pyproject.toml`+`uv.lock` (mypy v2), bim frontend `package.json`+lock (vite-plugin-svelte 7.3.0). **Zero Python-source changes since the PRDs' grounding was verified**, so every in-repo file/line claim carries.
- **mypy v2 landed** (`ee8d7ea`, PR #104, merged 2026-08-09) — the PR the 08-07 triage said to "hold hardest." Overtaken by events, and benignly: master's full Test run (which includes `uv run mypy src/lib/ src/tools/` at `test.yml:103`) is **green** on that commit and on every commit since, including setup-uv v10 (2026-08-12). `pyproject.toml` now pins `mypy>=2.3,<3`. The klyreon/postup "mypy strict green" gates are grounded against mypy v2, and the pyproject/uv.lock batch-contention risk from #104 is gone — it landed before the batch.
- Fresh spot checks (all pass): `pybase/filesystem` still has no `atomic_write` (positive control: `FileMetadataReader` export) — 00041 still needed; `MarkdownZettelRepository.save` still bare `write_text` at `:55`; `src/tools/pidash/` still present (00071 premise); tracon live at `~/.claude/skills/run-autopilot/scripts/tracon/`; `~/.claude/skills/brief-portfolio/scripts/collect.py` present; `dev/bin/check_tool_wiring.py` present; `scaffold.py --multi-interface` exists (`scaffold.py:333`); klyreon spec sentence still at `zettel-format-specification.md:118`; CI coverage gates intact (`test.yml:128` lib 80%, `:158` tool 50%); `~/.claude/metrics/costs.jsonl` live (00072); seam spec `dev/local/specs/all-interface-architecture.md` exists (00053/00054/00057 launch precondition); brush-report contract in 00063 matches the live collector (`collect.py:19,213-214`).
- `claude --help` re-run today: `-p/--print`, `--output-format json`, `--json-schema`, `--model`, and `--tools` with the documented `Use "" to disable all tools` semantics all present — 00075's pinned invocation is grounded as of 2026-08-14.
- Citation check (`check_links.py`): one hit under `backlog/` — 00076:41 `~/.claude/skills/klyreon/`, the install target the PRD itself creates. Waived forward reference, same as 08-07.
- Mechanical lens-A sweep (scripted): all 31 filenames match `NNNNN-{slug}-v{n}.md`; sequence numbers unique across `backlog/`, `hold/` (00049, 00059, 00069), `done/` (00051), `discovery/` (00062, 00073); frontmatter fields all recognized with valid values; task-line vs `Acceptance:` counts match in every PRD; `#### Feature:` headings unique per PRD; no `TBD`/`TODO`/`???`/`(guess)`/`{...}` stubs (the sweep's 10 raw hits were the domain word "todo(s)" in postup PRDs, confirmed false positives by reading each).

## Map

Unchanged from 08-07 except the two verdict changes marked ●.

| # | PRD | template | subsystems | depends on | verdict |
|---|-----|----------|------------|------------|---------|
| 00041 | atomic-write foundation | minimal | lib/filesystem, zettel, updater, bim doc | — (feeds 56, 63, 74) | READY |
| 00042 | bim serve confinement+auth | standard | bim serve + frontend | — | READY |
| 00043 | bim doc promote collision | minimal | bim doc | — | READY |
| 00044 | bim doc claim/dedup | minimal | bim doc | — | READY |
| 00045 | dot rm safety | minimal | dot | — | READY |
| 00046 | dot TUI secret status (#92) | minimal | dot | — | READY |
| 00047 | updater fail-loud | minimal | lib/updater | — | READY |
| 00048 | fctracker integrity | minimal | fctracker | — | READY |
| 00050 | zettel scanner errors | minimal | lib/zettel | — | READY |
| 00052 | decouple pybase from Click | minimal | lib/configuration, updater | — | READY |
| 00053 | dot git-ops unification | standard | dot | seam spec (exists) | READY |
| 00054 | bim serve/TUI convergence | standard | bim serve, tui, frontend | seam spec, 00042 | READY |
| 00055 | bim cli modularization | minimal | bim | soft: after 00054 | READY |
| 00056 | bim doc migrate-layout | minimal | bim doc | 00041 | READY |
| 00057 | bim doc triage review | minimal | bim doc + serve | seam spec, 00043, 00044 | READY |
| 00058 | dot diff-layout extraction | minimal | dot TUI | — | READY |
| 00060 | delete dead code | minimal | lib, tools, docs, packaging | — | READY |
| 00061 | prune formatting | minimal | lib/formatting, bim | — | READY |
| 00063 | postup A: scaffold + collector | standard | postup (new) | 00041 | READY |
| 00064 | postup B: enrich | standard | postup | 00063 | READY |
| 00065 | postup C: web core | standard | postup | 00063, 00064 | READY |
| 00066 | postup D: web views | standard | postup | 00065 | ● **FIX (F1)** |
| 00067 | postup E: serve | standard | postup | 00065, 00064 | READY |
| 00068 | postup F: TUI + brief | standard | postup | 00063, 00065 | READY |
| 00070 | postup G2: brief-portfolio cutover | standard | postup | 00064, 00067, 00068 | READY |
| 00071 | retire pidash | minimal | pidash removal | — | READY |
| 00072 | meta-budget share in postup | standard | postup | 00065, 00068 | ● **FIX-optional (F3)** |
| 00074 | klyreon A: core + vault | standard | klyreon (new) | 00041 | READY |
| 00075 | klyreon B: ingest | standard | klyreon | 00074 | READY |
| 00076 | klyreon C: operator assets | standard | klyreon | 00074 | READY |
| 00077 | klyreon D: maintain + schedule | standard | klyreon | 00074, 00075, 00076 | READY |

## Findings

### Blocking

**F1. [00066] Lens B — acceptance criterion depends on a PR that the unattended pipeline never creates.**
Location: 00066:143, Phase 2 task "SPA parity sweep": "Acceptance: every SPA component's information content mapped to a new view **(checklist in PR)**; gates green."

Autopilot lands feature work as direct commits on master — verified against git history: every `feat` commit (morph pdf2png, sysup, bim, the whole pidash hook series) carries no PR reference; only renovate/dependabot commits do. There is no PR in the loop, so the checklist's designated home does not exist at execution time. The test author and blind reviewer (Blake) hold acceptance criteria verbatim; a criterion naming an artifact surface the pipeline cannot produce is either improvised around (implementer picks a different home) or failed (reviewer cannot find it). Missed by both prior gates; same mechanism class as 08-07's B4 (exit criterion pointing at something the reviewer cannot verify). **Fails as: rework thrash.** Fix: repoint the parenthetical at an artifact the loop does produce — `dev/local/audit-results/` (the 00070 parity precedent) or the task's commit message.

### Questions

**F2. [batch environment] Renovate re-armed auto-merge on #140 and #117 — the two PRs the 08-07 triage disarmed.**
Location: GitHub PRs #140 (lock-file maintenance, touches `uv.lock`), #117 (patch all-non-major, rust + bim frontend). Not a PRD defect — a pre-launch decision.

`autoMergeRequest` shows renovate re-enabled auto-merge on both at 2026-08-09 12:55–12:56, hours after the triage's `gh pr merge --disable-auto`. Disarming via gh does not survive renovate's next run. Both are currently **red** (#140 fails lint; #117 fails the whole lib matrix), so neither merges today — but renovate rebases on schedule, and the first rebase that goes green squash-merges into master unattended. #140's `uv.lock` collides with the batch's own lock edits (00063+, 00067 extras, klyreon wiring): master moving mid-batch means non-fast-forward pushes and lock-file conflicts inside the unattended loop. Options walked in the session; decision recorded below. Related: #115 (mypy `<3` range widen) is now moot — pyproject already pins `mypy>=2.3,<3` after #104; #145 (pyo3 0.29.2, Cargo-only) is new and batch-inert.

### Non-blocking

**F3. [00072] Lens E — structural decomposition names directories that conflict with the postup layout the set establishes.**
Location: 00072 Repository Structure: `src/tools/postup/collectors/meta_share.py` and `views/`.

00063 fixes postup's layout as `domain/` (pure logic), `adapters/` (subprocess + CLI/web/tui), `commands/`, `params/`; 00064–00068 all extend that shape. 00072 — written the day after 00063 — invents `collectors/` and `views/` instead. Its acceptance criteria are path-free and design-solution runs for this PRD, so the loop survives (that keeps it Non-blocking), but a planner following the PRD verbatim creates a third naming scheme inside one tool, and a blind reviewer comparing built paths against the PRD's tree flags the mismatch. Fix: repoint the tree and module blocks at `domain/meta_share.py`, the 00065 frontend for the web tile, and the 00068 brief renderer for the text tile.

### Re-verified, no finding

- Human-in-the-loop sweep re-run: every "manual" hit is a documented post-merge smoke (00042/00054/00067), a documented out-of-gems follow-up (00070), problem-statement prose (00057), or error-message content (00077). Zero "open question" hits. The 00064/00067 "open decision (design)" items are resolved autonomously by Phase 1.5 — cleared by both prior gates, unchanged.
- All cross-PRD dependencies point at lower numbers; no same-file contention beyond the sequenced 00042→00054 and 00047→00052 pairs, both with explicit preserve-the-earlier-fix language.
- 08-07 apply-pass edits all present in the files (00070 rescope banner, 00071 minimal-template rebuild, 00077 MOC-sync feature/module/task/metric, 00072 stub removal, 00075 pinned claude invocation, 00041 pidash-repoint correction, N4 frontmatter).

## Reshapes

None.

## Gaps

No new producer/consumer holes, half-migrations, or dropped must-haves. Operational (outside this gate's edit mandate), updating the 08-07 dep-PR triage:

- Merged since: #104 (mypy v2), #146 (vite-plugin-svelte 7.3.0), #147 (setup-uv v10) — all green on master.
- Open: #145 (new, Cargo-only, inert), #140 + #117 (**auto-merge re-armed by renovate, currently red** — see F2), #131 (typescript v7, contends with 00042/00054 frontend), #120 (serde_yml, breaking, needs code work), #116/#103 (ocrmypdf pair), #115 (moot post-#104).

## End state after this batch

Unchanged from 08-07: klyreon lands as tool 17 (autonomous Memex-Zettelkasten), postup as the first all-four-interfaces gem absorbing the portfolio brief, all five AGENTS.md invariant GAPs close (41, 42, 44, 52, 53/54/57), pidash retires with tracon named as successor, brief-portfolio skill retires on parity evidence. Autopilot monitoring lives only in the buvis repo.

## Frontmatter tuning

None new; 08-07's tuning (00074 `design_gate: user` + `rework_cap: 3`, 00075 same, 00077 `rework_cap: 3`, 00071 `catchup: skip` + `design: skip`) verified in place.

## Decisions applied

All three findings walked attended 2026-08-14/15; F1 and F3 took the Recommended option, F2 took a user-directed option ("solve what causes the PRs to be red").

1. **F1 — applied.** 00066:143 now reads "(checklist written to `dev/local/audit-results/spa-parity-<date>.md`, the 00070 parity-artifact precedent)". Lens A re-run on the file: task/acceptance counts match, headings unique, no stubs. 00066 → READY.
2. **F2 — root causes fixed on master** (user-directed: not disarm, not config freeze — make the PRs green so they land *before* the batch; both PRs are renovate-Immortal, so merging was the only durable exit anyway):
   - `4ff15cd` `chore(lint)`: ruff 0.16 adaptation — PLR0917 suppressions extended on the two policy-suppressed sites (`click_integration.py`, `account.py`), `PLR0917` added to the tests per-file-ignore, RUF036 union order fixed in `bim/cli.py`; locked ruff bumped to 0.16.3 **and** the pre-commit hook rev bumped v0.11.12 → v0.16.3. The rev bump is load-bearing: the old hook's RUF100 auto-fix silently stripped the PLR0917 suppressions on the first commit attempt (three-way version skew: hook 0.11 / lock 0.15 / CI-on-#140 0.16).
   - `5e9ad84` `build(deps)`: zettel-core migrated to serde_yml 0.0.13 (Mapping keys now `String`, infallible `as_f64`, `TaggedValue` accessor; Cargo pin + lock bumped). Verified: `cargo test` 33/33; `.so` rebuilt locally and `pytest -m lib` 1383 passed incl. the Rust↔Python parity suite; `-m fctracker` 56, `-m bim` 1067, `mypy` clean over 453 files, ruff 0.16.3 check + format clean. **Bonus**: serde_yml ≤0.0.12 carried RUSTSEC-2025-0068 (unsound serializer); 0.0.13 removes the vulnerable surface, so the migration clears a security advisory too.
   - Rebase checkboxes ticked on #140 and #117; both auto-merge on green. Dependabot #120 (same serde_yml bump) is superseded by `5e9ad84` and will self-close; #115 (mypy range) already moot post-#104.
   - Follow-ups surfaced, not silently done: (a) serde_yml 0.0.13 is an end-of-life shim backed by noyalib — a deliberate migration to a maintained crate (noyalib compat mode / serde-saphyr) deserves its own small PRD; (b) the new backend parses YAML 1.2 strict booleans, so 1.1-style `yes/no/on/off` literals now stay strings in the Rust path while PyYAML still reads them as bools — no committed fixture exercises them (parity suite green), but a parity fixture pinning the intended semantics would close the latent class; (c) `cargo clippy -D warnings` reports 24 pre-existing findings across untouched files (match-like-matches, manual-strip, redundant-closure, type-complexity...) — clippy is not a CI gate today; left untouched per surgical-changes, named here for a future hygiene pass.
3. **F3 — applied.** 00072's tree now maps `domain/meta_share.py` + the 00065 web frontend + the 00068 brief renderer; module blocks renamed (`postup.domain.meta_share`, "brief tiles") and the dependency-graph labels updated to match. Lens A re-run: clean. 00072 → READY.

Final state: **31 PRDs in `backlog/`, all READY. Verdict GO.** F2 closed end to end on 2026-08-15: master CI green on the fix commits (run 31845297575), then both rebased PRs auto-merged with zero check failures — #117 first, then #140 — and local master fast-forwarded to `fa574f1`. Aftermath note: the stale mise-global `pipx:ruff` 0.15.22 on PATH re-stripped the PLR0917 suppressions once more post-commit (background fixer); files restored from HEAD and the global upgraded to 0.16.3 (`mise install pipx:ruff@latest --force` — plain `mise upgrade pipx-ruff` matches nothing and reports vacuous success). Batch launch is unblocked.
