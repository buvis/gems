# Discovery: postup — Portfolio Standup Gem

## Classification
Depth: comprehensive | Date: 2026-07-13 | Status: PRDs created 2026-07-13 (00063–00070 in backlog; 00049/00059 moved to hold/ as merge-absorbed)

## Problem
The portfolio status brief lives as a Claude Code skill
(`~/.claude/skills/brief-portfolio/`): a stdlib Python collector + template
builder plus a Svelte 5 SPA baked into one HTML file, with Claude hand-writing
`epics.json` (narrative, epic grouping, judgment todos). It only runs inside a
Claude Code session, escapes every gems quality attribute (tests, typing, CI,
release, docs), and its LLM step is welded to one agent. Separately, pidash
(the autopilot PRD-cycle TUI) overlaps the same "what is my portfolio doing"
territory and is the repo's biggest fix magnet. Goal: one gem, `postup`, that
runs fully without any LLM, unlocks narrative/judgment features when the
`claude` CLI is available, absorbs pidash, and carries all four gem
interfaces.

## Requirements

### Must have
- New gem `postup` (POrtfolio STandUP, mirrors sysup naming) at
  `src/tools/postup/`, scaffolded per gems conventions (multi-interface
  layout), `manifest.toml` declaring **cli/tui/rest/web**, entry point
  `postup.cli:cli`, extras wired in root `pyproject.toml`.
- **Deterministic collector** (`postup collect`): port of `collect.py`
  behavior — commits/releases/last-tag/unreleased, issues, PRs, CI runs,
  security alerts, stray branches/worktrees, PRD pipeline
  (`dev/local/prds/{backlog,wip,done}`), CHANGELOG unreleased, brush
  hygiene recency (`dev/local/audit-results/brush-report.md` `generated:`
  date → 30-day brush-cadence todo), local branch/dirty/ahead-behind/stashes,
  external review-requested/authored —
  via `git` + authenticated `gh` CLI delegation, parallel across repos,
  `--no-fetch` fast path (parity with today's collector flag), per-repo
  `errors[]` degradation, WARNs through the console adapter.
  Outputs stay file-based contracts: `data.json` (typed, **versioned**),
  `commits-digest.md`, `data-prev.json` rotation, `history.jsonl` append.
- **Repo discovery**: scan a settings-defined list of root directories for
  `.git`, minus a settings-defined exclusion list of repo paths. No gita
  dependency.
- **LLM enrichment** (`postup enrich`): `claude -p` shell-out; detect
  availability; alert the user it will be used; warn that quality suffers
  without it and continue deterministically. Model user-configurable. The
  enrichment prompt and epic/todo rules move from the skill into the gem.
  `epics.json` validated against a pydantic schema (summary, per-repo epics
  with exact SHAs, judgment todos with stable ids, urgency,
  importance/effort).
- **Web** (`postup serve`): FastAPI + uvicorn (optional extra, bim-serve
  pattern) serving a **SvelteKit rebuild** of the SPA — Brief, Todo, Matrix,
  Repos, Activity, Work, PRDs tabs, RepoDetail, attention Horizon,
  since-last diff, trend sparkline, done-state — with SSE and
  collect/enrich-from-UI. Localhost-only confinement matching the 00042
  posture (path confinement, TrustedHost, auth per bim conventions).
- **TUI** (`postup tui`): Textual standup — attention queue, todos, repo
  list — snapshot-tested on the canonical env.
- **CLI brief renderer**: bare `postup` (and `postup brief`) prints the
  deterministic text standup — attention queue, mechanical todos, repo
  summary, since-last diff — from the latest `data.json`; no Textual
  import on the default path.
- **pidash absorption**: portfolio-wide autopilot PRD-cycle view (web +
  TUI): phase, cycle, reviewer/attention state per repo. Overtakes the two
  backlog PRDs:
  - from **00049**: hook state writes are durable and serialized from day
    one — flock sidecar around every state read-modify-write,
    fsync-before-replace, `pybase.filesystem.atomic_write` underneath,
    hooks-install preserves existing entry order; concurrent-writer
    regression tests.
  - from **00059**: the autopilot `state.json` reader parses via an
    explicit **versioned** pydantic model (`schema_version`,
    unknown-version handled loudly), contract-tested against
    representative payloads; Textual snapshot tests are the layout gate;
    doc note naming the schema as the shared contract with the autopilot
    skill.
  - pidash retires in this set: tool dir, entry point, extras, docs page,
    tests removed; CHANGELOG Removed entry; note that installed hook copies
    under `~/.claude/hooks/` need a `postup hooks install` re-deploy.
- **Cutover**: data-level parity check on the real portfolio — on the
  same portfolio snapshot, `postup collect` covers the same repo set and
  per-repo signal fields as the skill's `collect.py` (semantic diff;
  naming/shape mapping allowed; narrative/epics excluded — LLM
  nondeterminism); web/TUI sanity-checked by eye per Q9. Then delete
  `~/.claude/skills/brief-portfolio/` (buvis home repo — out-of-gems
  follow-up step, documented in the final PRD).
- **gems gates** on every PRD: per-gem pytest marker, >=50% tool coverage,
  mypy strict, ruff, CI matrix, Sphinx page under `docs/source/tools/`,
  Keep-a-Changelog entries prefixed `postup`/`pidash`, lazy imports for
  heavy optional deps.

### Nice to have
- Server-side done-state persistence (JSON in the out dir) replacing
  localStorage, now that serve is the only web delivery.
- Auto-open browser on `postup serve`.

### Out of scope
- Non-GitHub forges (GitLab/Gitea) — `gh` stays the forge layer.
- Legacy state migration from `~/.claude/portfolio-brief/` (trend/diff
  restart from zero).
- Single-file HTML export — dropped; `postup serve` is the only web
  delivery.
- Remote/multi-user serving, built-in scheduling, Python GitHub SDK.

## Constraints
- Python >=3.11 inside the single `buvis-gems` package; uv; Click CLI;
  pydantic-settings (`PostupSettings(GlobalSettings)`, env prefix,
  `--config`); `buvis_options` decorator.
- CommandResult discipline (commands return success AND failure results;
  only adapters render); console adapter for all output — no `print`,
  `click.echo`, or `logging`; never leak tracebacks.
- All-interface rule: one action, one implementation through the
  composition root (00051 seam design; code toward the 00052
  pybase-Click-decouple target state).
- Atomic persistence via `pybase.filesystem.atomic_write`; request-derived
  paths confined per AGENTS.md invariants.
- LLM strictly optional at runtime; no cloud AI SDK; `claude` CLI shell-out
  is the only LLM path.
- Authenticated `gh` CLI required for forge data; absence degrades per-repo
  into `errors[]`, never a crash.

## Codebase Context
- **Source being ported**: `~/.claude/skills/brief-portfolio/` —
  `scripts/collect.py` (361 lines, stdlib-only), `scripts/build.py` (55
  lines, payload injection), `app/` Svelte 5 + Vite SPA (2,551 lines: 12
  components, `lib/derive.js` 345 lines of pure logic with the only test,
  plain `node:assert`), `assets/template.html` (built bundle). One
  localStorage key (`brief-portfolio-done`, pruned by payload ids).
- **Gem exemplars**: `src/tools/bim/commands/serve/` (FastAPI app factory,
  `_routes.py`, `_sse.py` via watchfiles, SvelteKit frontend subtree with
  committed build, `bim-web` extra); `src/tools/pidash/` (Textual TUI,
  Claude Code hook installer, `tui/state.py` state reader — the absorption
  target); `src/tools/sysup/` (abbreviation naming precedent);
  `src/tools/hello_world/` + `dev/bin/scaffold.py --multi-interface`
  (structure).
- **Integration points**: root `pyproject.toml` ([project.scripts], wheel
  packages, extras, pytest markers via `tests/conftest.py`),
  `.github/workflows/test.yml` path-filter, `docs/source/tools/*.rst`,
  `CHANGELOG.md`, `AGENTS.md` invariants (HOLDS/GAP).
- **Superseded backlog PRDs**: `00049-pidash-hook-durability-v1.md`,
  `00059-pidash-state-schema-contract-v1.md` — move from
  `dev/local/prds/backlog/` to `hold/` when the absorbing postup PRD set
  is created; their requirements are folded in above.

## Approach
- **Chosen**: full gem port in **8 session-sized PRDs** with explicit
  blocked-by guards (autopilot auto-pick has no dependency awareness):
  - **A. scaffold + collector** — gem skeleton, settings
    (roots/excludes/out-dir/model), collector port, typed versioned
    data.json contract, rotation/history. No deps.
  - **B. enrich** — claude CLI adapter, prompt, epics schema, alerts,
    degradation. Needs A.
  - **C. web frontend pt. 1** — SvelteKit subtree per bim layout, payload
    plumbing, derive-logic port (+ its tests first), Brief/Todos/Repos,
    done-state. Needs A (fixture payloads).
  - **D. web frontend pt. 2** — Matrix/Activity/Work/PRDs, RepoDetail,
    Horizon, since-last/trend. Needs C.
  - **E. serve** — FastAPI factory, REST routes, SSE, collect/enrich
    trigger, confinement, extras wiring. Needs C.
  - **F. TUI + text brief** — Textual standup + snapshot tests; bare
    `postup` text renderer sharing the same Python derive layer. Needs A.
  - **G1. absorbed data layer** — durable hook layer + `postup hooks
    install` (00049 obligations), versioned state-reader contract + tests
    (00059 obligations). Needs A only — lands early so the hook data-loss
    fix does not wait on the frontend chain.
  - **G2. cycle views + retirement + cutover** — portfolio-wide cycle
    view (web + TUI), pidash retirement, parity check, skill deletion
    follow-up. Needs B, E, F, G1.
- **Why**: keeps every PRD reviewable and autopilot-sized; deterministic
  core lands first and is useful alone; LLM, web, TUI, and absorption
  layer on independently.
- **Rejected alternatives**:
  - Static single-file delivery (original skill model) and serve+export
    hybrid: user dropped export entirely — serve is enough; kills the
    SvelteKit-inlining problem.
  - Ollama or cloud-SDK enrichment: gems has no cloud-AI precedent; user
    chose `claude -p` delegation (matches the gh-CLI pattern); Ollama
    quality insufficient for judgment todos.
  - Porting the Svelte 5 SPA as-is: rejected to keep one frontend
    convention (SvelteKit, bim) in the repo despite the larger rewrite.
  - gita CSV registry (current source): rejected for roots+excludes
    auto-discovery in settings; drops the gita coupling.
  - Thin trigger skill / keep-both transition: skill gets deleted at
    parity; no parallel implementations.
  - 4-or-5 fat PRDs: C+D as one PRD risks context overflow on a
    2,500-line rewrite.

## Success Criteria
- With no `claude` on PATH and no LLM anywhere: `postup collect` + every
  interface renders the full deterministic brief, each on its own surface
  (all tabs, mechanical todos, since-last diff, trend on the web), for
  the real portfolio.
- With `claude` present: `postup enrich` yields narrative/epics/judgment
  todos passing schema validation; the user is alerted which mode ran.
- TUI shows the standup and the absorbed PRD-cycle view; pidash is gone
  from the repo (no tool dir, entry point, extra, or docs page).
- Superseded PRDs 00049/00059 removed from the backlog with their
  obligations demonstrably covered (concurrent-writer test, state contract
  test, snapshot gate).
- All gems gates pass: per-gem pytest marker green, >=50% coverage, mypy
  strict, ruff, CI matrix, Sphinx page, CHANGELOG entries, extras
  installable (`uv tool install buvis-gems[postup...]`).

## Risks
- **`claude -p` fragility** (invalid JSON, latency, quota): pydantic
  validation with one retry, then loud degradation to deterministic mode;
  never block the brief on enrichment.
- **Frontend rewrite regressions** (only derive.js is tested today): port
  derive logic and its test suite first against fixture payloads; per-view
  tests in C/D.
- **PRD G breadth** (hooks durability + state contract + views +
  retirement): resolved — split into G1 (data layer) + G2 (views +
  retirement + cutover) in Approach.
- **Backlog interactions**: 00049/00059 move to `dev/local/prds/hold/`
  (merge-absorbed originals) when the postup PRD set is created; restore
  from hold/ if the set is abandoned (folder-qualified, per the
  cancelled-PRD numbering hazard); 00052 (pybase-Click decouple) may land
  mid-set and shift the composition-root seams — postup codes to the
  target state.
- **gh rate limits / API flakiness** on large portfolios: carried-over
  behavior — per-repo `errors[]`, WARN surfacing, `--no-fetch` fast path.

## Open Questions
- REST route surface for serve (payload read, collect/enrich triggers, SSE
  channels, done-state endpoint) — design-solution decides, with bim's
  action-registry pattern (the AGENTS.md exemplar) as the default
  candidate.
- Done-state home: server-side JSON vs localStorage now that serve is the
  only delivery (recommend server-side; decide in design).
- Autopilot state discovery for the cycle view: confirm pidash's actual
  state source paths (per-repo autopilot `state.json`, per-session mirror
  files) while scoping G1/G2.
- Claude model default (pin one vs inherit CLI default) and digest-size
  strategy for large portfolios (chunk the prompt or cap commits).
- Extras naming: single `postup` extra vs `postup` + `postup-web` split
  (fastapi/uvicorn/watchfiles) and where textual lands — follow bim
  precedent at wiring time.
- Out-dir default: XDG data dir (`~/.local/share/postup/`) vs current
  `~/.claude/portfolio-brief/` — settings default, decide in PRD A.
- Whether `postup serve` auto-collects on start or serves last data until
  refreshed.

## Discovery Log

### Q1: What should the delivery/serving model be?
**Answer**: Serve + static export — `serve` command (FastAPI + uvicorn + SSE,
optional extra, bim precedent) with refresh-from-UI, plus keep the single-file
HTML export. **Amended by Q11: export dropped; serve is the only web
delivery.**

### Q2: How should the LLM-optional features be powered?
**Answer**: Via the `claude` CLI (`claude -p` headless calls), not Ollama and
not a cloud SDK. Detect availability; alert the user it will be used; warn
that quality suffers without it and continue deterministically. User picks
the model (configurable). Hard requirement: no dependency on the Claude Code
skill — the prompt and everything else the skill owns moves into the gem.

### Q3: Gem name?
**Answer**: **postup** (POrtfolio STandUP), chosen after two variation rounds
(user wanted an abbreviation of "portfolio standup" / "portfolio situation
report"). Binary `postup`; module `src/tools/postup/`.

### Q4: What happens to the Claude Code skill once postup ships?
**Answer**: Delete `~/.claude/skills/brief-portfolio/` entirely once the gem
reaches parity. No thin trigger skill.

### Q5: Frontend — port the Svelte 5 SPA or rewrite on SvelteKit?
**Answer**: Rewrite as SvelteKit, mirroring bim's frontend subtree, keeping
one frontend convention in the repo. (Export-inlining consequence dissolved
when Q11 dropped the export.)

### Q6: Where does postup get its repo list?
**Answer**: Auto-discover from a list of root directories in postup settings
(scan for `.git`), with an exclusion list of repo directory paths. No gita
dependency.

### Q7: What is OUT of scope for v1?
**Answer**: Non-GitHub forges; legacy state migration. Accepted baselines:
localhost-only single-user serving (00042 posture), no built-in scheduler,
GitHub via authenticated `gh` CLI. TUI and pidash consolidation left in
scope (confirmed in Q8).

### Q8: Scope check — TUI and pidash consolidation confirmed in scope?
**Answer**: Both in v1. postup ships all four interfaces (first full
all-interface gem) and absorbs pidash; pidash retires in this PRD set.

### Q9: Success criteria?
**Answer**: Baseline set (deterministic parity without LLM; validated
enrichment with `claude`; TUI + absorbed cycle view with pidash gone; gems
gates). No perf budget, no formal visual-parity checklist. (Export criterion
dropped with Q11.)

### Q10: PRD decomposition?
**Answer**: 7 session-sized PRDs (A–G) with explicit blocked-by guards, as
laid out in Approach. **Amended in review: G split into G1 (absorbed data
layer, needs A) + G2 (cycle views + retirement + cutover, needs B/E/F/G1)
— 8 PRDs total.**

### Q11: Remaining risks / final adjustments?
**Answer**: Two changes: (1) **drop the single-file export** — the serving
command is enough; (2) **overtake the planned pidash PRDs** — backlog
00049 (hook durability) and 00059 (state schema contract) fold into the
postup set and retire when their successor PRD is created. Identified risks
otherwise accepted as listed.
