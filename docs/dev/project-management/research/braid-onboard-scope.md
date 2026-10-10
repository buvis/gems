# Braid / `onboard` tooling — scope & open questions

Status: **scoping only** (2026-10-04). No code. Grounds the last unbuilt piece of
the AI-age repo-structure adoption (`/Users/bob/.kiro/crew/workspace/ai-age-repo-structure.md`,
decisions 3/4/5, decision-7 Kiro leg, and the `onboard` behavioral contract).

## What `onboard` is for

`onboard` is the **one setup/repair command** (a `tools/onboard` shim → mise
`onboard` task). It does **not** author anything; it projects and wires what the
repo already declares:

1. **Skill projection** — call Braid (in `agent-skills`) to project committed
   `.agents/skills/` into each enabled host's native skill dir (`.claude/skills`,
   `.kiro/skills`, …), gitignored, symlink-with-copy-fallback.
2. **Kiro specs link** (optional) — symlink/junction the canonical specs folder
   (read from `.agents/specflow.json`) into Kiro's expected location. Never a copy.
3. **Hook composition** — install only onboarding-owned hook entries at the
   effective `core.hooksPath`, composing with the existing manager, never clobbering.
4. **Prerequisites** — install declared deps via mise/toolchain (full `onboard` only).

`onboard --sync` is the lightweight subset git lifecycle hooks call: refresh local
projections only; no dep install, no network, no tracked-file edits.

## gems' current state (checked 2026-10-04)

| Contract input | gems today | Implication |
|---|---|---|
| `.agents/skills/` (canonical project skills) | **ABSENT** — none committed | **onboard has nothing to project in gems yet.** This is the headline finding. |
| mise `onboard` task + `tools/onboard` shim | absent (only `release`) | greenfield for this repo |
| Hook manager | `pre-commit` (`.pre-commit-config.yaml`), `core.hooksPath` = default `.git/hooks` | onboard must compose with pre-commit, not replace it |
| `.agents/specflow.json` | present (`root`+`specsDir`) | Kiro specs-link input is ready IF Kiro is enabled |
| Braid (`agent-skills`) | checked out at `~/git/src/github.com/buvis/agent-skills` | the projection engine exists; needs repo-isolation mode (below) |
| Enabled hosts (per capability table) | AGENTS.md + CLAUDE.md only; no `.kiro`/Kiro editor | **Kiro leg not enabled for gems** → specs-link + Kiro skill projection are out of scope here |

**Scoping consequence:** for gems *specifically*, onboard's only live jobs would be
(a) hook composition with pre-commit and (b) dep install — skill projection and the
Kiro link are both no-ops until gems commits skills and/or enables Kiro. So the
honest question is **whether gems is even the right first adopter**, or whether
onboard should debut in a repo that actually projects skills (postup/klyreon ship
Claude skills today).

## Work breakdown

### A. Braid repository-isolation mode (in `agent-skills`, the hard prerequisite)
The design (decision 3) says the current Braid CLI is **not** repo-isolated:
"destination overrides alone still include personal sources." Required before onboard
can call it safely:
- A repo mode using only the repo's declared sources/targets — must NOT implicitly
  pull in `~/.claude` personal skills, global policy, or Braid's own source checkout.
- State/backups local, gitignored, scoped to the working tree (shared git hook
  storage across worktrees must not cross-contaminate).
- A fresh clone must not require a sibling `agent-skills` checkout — the dependency
  is declared by the repo's tooling (how? see open Q3).
- Reuse existing inventory/ownership/backup/link/drift machinery; reconcile with
  Braid's in-flight hardening before expanding automatic use.

### B. `onboard` mise task + shim (per-repo, the contract above)
- `tools/onboard` shim → mise `onboard` task (verb-first name; mind Bash builtin
  collisions per decision 4).
- Implement the 8-step contract: resolve worktree via git (not hard-coded
  `.git/hooks`; `.git` may be a file; worktrees share hook storage), prereqs,
  hook composition, host selection (reliable Kiro detection — NOT `~/.kiro/`
  existence), ignore coverage, Braid repo-mode call, Kiro specs link, report.
- `--sync` subset for hooks; idempotent; reports unowned conflicts instead of
  overwriting.

### C. Common command vocabulary (decision 4, smaller)
Add `check`, `format`, `run-tests`, `build`, `develop` mise tasks + shims where
applicable, matching names CI reuses. Partly independent of A/B — could ship first
as a low-risk warm-up.

## Open questions (must resolve before building)

1. **Kiro skill-discovery target (RESOLVED as "verify at build time", still unverified).**
   Does onboard's Kiro leg target a repo-local `.kiro/skills/`, a `skill://` ref, or
   a copy into user-global `~/.kiro/skills`? Needs a probe against a **real Kiro
   install** before Braid advertises the adapter. **Hard gate: detect the Kiro
   *editor* by its binary on PATH or a Kiro-specific marker — `~/.kiro/` existence
   false-positives on every KiroCrew box** (it is also KiroCrew's config root). Not
   blocking for gems (Kiro not enabled here).

2. **First adopter — gems or a skill-shipping repo? → DECIDED 2026-10-04: klyreon.**
   gems projects zero skills, so onboard's main value (skill projection) is untested
   there. **klyreon** is the debut adopter: it ships exactly one clean, recently-built
   Claude skill (`assets/payload/claude/skills/klyreon/SKILL.md`), the smallest *real*
   projection case (postup has a larger skill history). All of A/B lands and is tested
   against klyreon first; gems adopts later once it has skills or enables Kiro.

3. **How does a repo declare its Braid dependency** such that a fresh clone needs no
   sibling `agent-skills` checkout? (mise-installed tool? vendored? pinned release?)
   The design states the requirement but not the mechanism.

4. **pre-commit composition mechanism.** gems uses pre-commit with default
   `.git/hooks`. How does onboard install an owned `post-checkout`/`post-merge`/
   `post-rewrite` → `onboard --sync` entry **without** fighting pre-commit's own
   hook installation? (pre-commit manages `.git/hooks/*`; need a composition seam,
   e.g. pre-commit's own `post-checkout` stage, or a chained owned entry.)

5. **Copy-adapter drift.** Where symlinks are unavailable (Windows no-dev-mode),
   onboard copies — but git lifecycle hooks only fire on checkout/merge/rewrite, not
   ordinary source edits. How is a stale copy detected and refreshed on an edit?
   (Design says "report stale copies and refresh explicitly" — needs a concrete
   drift check.)

## Recommended sequencing

1. **Resolve Q2 + Q4 + Q3 first** (first adopter, pre-commit seam, dependency
   mechanism) — these shape everything and are decisions, not code.
2. **C (command vocabulary)** as a low-risk standalone warm-up if desired.
3. **A (Braid repo-isolation)** — the real engineering, lands in `agent-skills`,
   its own PRD + tests.
4. **B (onboard task)** last — it's the thin coordinator once A exists.

Kiro-leg work (Q1) stays parked until a real Kiro install can be probed and a
skill-shipping repo enables it.
