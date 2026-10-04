# postup G2: brief-portfolio cutover

<!-- design; migrated from PRD 00070 flat file -->

## Structural Decomposition

### Repository Structure

```
tests/tools/postup/
└── test_parity.py                 # Maps to: Data-level parity check
dev/bin/
└── parity_brief_portfolio.py      # Maps to: Data-level parity check (comparison runner)
dev/local/audit-results/
└── brief-portfolio-parity-<date>.md   # Maps to: Data-level parity check (recorded artifact)
```

### Module: parity comparison
- **Maps to capability**: Cutover
- **Responsibility**: Compare the two collectors' outputs field-by-field and report coverage. No UI, no deletion.
- **Exports**:
  - `compare(skill_output, postup_output)` - per-field coverage result with the missing set
  - `render_checklist(result)` - the recorded artifact body

## Dependency Graph

### Foundation Layer (Phase 0)
External: 00064, 00067, 00068 must be in `done/`.

- **parity comparison**: depends only on the two collectors' output shapes — built first.

### Core Layer (Phase 1)
- **real-portfolio parity run**: depends on [parity comparison]

### Integration Layer (Phase 2)
- **skill-deletion follow-up documentation**: depends on [real-portfolio parity run]

## Test Strategy

### Critical Scenarios
- **Happy path**: fixture outputs covering the same signal fields under different names → Expected: parity passes with the naming map recorded.
- **Edge case**: postup output missing one per-repo signal field → Expected: parity fails naming that field; cutover blocked.
- **Edge case**: epic narrative text differs between runs → Expected: parity passes (content excluded); a missing or schema-invalid `epics.json` → Expected: parity fails.
- **Error case**: skill-deletion premise re-check finds the skill already gone or changed such that parity no longer holds → Expected: skip and report; nothing documented as complete.

## Risks

- **Premise drift on the skill** (it is actively used and may change): the deletion feature carries an execution-time premise re-check; skip-and-report, never force.
- **Parity repo-set mismatch** (gita registry vs postup's roots scan): the comparison run configures postup to the gita-derived set; a genuine set difference is a config note, not a parity failure.
- **The skill's layout has already moved** (it is now `app/`, `assets/`, `scripts/`, `SKILL.md`; `collect.py` sits at `scripts/collect.py`): the parity runner resolves the collector path at execution time rather than hardcoding a layout that has drifted once already.

## Completion notes (2026-09-29)

### Parity evidence — PASS

- Phase 0: comparison module `dev/bin/parity_brief_portfolio.py` (`compare` +
  `render_checklist`) with the fixture pair in `tests/tools/postup/test_parity.py`.
  The matching pair passes; a postup output missing a per-repo signal field fails
  and names it (top-level and nested sub-fields, e.g. `local.stashes`); narrative
  / commit-content differences do not fail; a missing or schema-invalid
  `epics.json` fails. `uv run pytest tests/tools/postup/test_parity.py` → 11 passed.
- Phase 1: both collectors run fresh 2026-09-29 over the gita-derived set
  (`~/.config/gita/repos.csv`), `--days 60 --no-fetch`. postup was configured to
  the skill's gita set exactly — `roots = github.com/{buvis,doogat,tbouska}` with
  the 11 non-gita repos under those parents excluded, so the two sets match
  (26 listed, 25 collected; `doogat/jink` skipped by both — no `origin` remote,
  a shared skip, not a gap). Recorded artifact:
  `dev/local/audit-results/brief-portfolio-parity-2026-09-29.md`.
- **Verdict: full coverage.** Every per-repo signal field the skill emits is
  covered by postup across all 25 repos; the portfolio-level external "my PRs"
  section is covered; enrichment is structurally covered (postup wrote a
  schema-valid `epics.json`). Skill-only keys `org` (= owner), `visibility`,
  `pushed_at`, `purge_last_run`, and issue `comments`/`reactions`/`milestone` are
  documented non-gaps (not portfolio-brief coverage signals).

### Skill-deletion follow-up — PREMISE DRIFTED, do NOT run the discovery command

Execution-time premise re-check (2026-09-29), per the discovery rule
"skip-and-report, never force":

- **Skill exists and parity holds: TRUE.** The collector resolved at execution
  time to `~/.claude/skills/brief-portfolio` →(symlink) `~/.agents/skills/brief-portfolio`
  →(symlink) `~/git/src/github.com/buvis/agent-skills/skills/brief-portfolio/scripts/collect.py`.
- **The buvis-tracked `git rm` premise is now FALSE.** Grounded 2026-07-13 /
  re-confirmed 2026-08-07, `.claude/skills/brief-portfolio` was a real directory
  **tracked by the buvis bare repo**, so the documented removal was:

  ```sh
  # STALE as of 2026-09-29 — buvis no longer tracks this path (returns 0 files):
  git --git-dir=~/.buvis --work-tree=~ rm -r .claude/skills/brief-portfolio
  ```

  As of 2026-09-29, `git --git-dir=~/.buvis ls-tree -r --name-only HEAD --
  .claude/skills/brief-portfolio` lists **0 files**: the path is now a **symlink**
  and the skill content lives in the separate **`agent-skills`** git repo
  (`git -C ~/git/src/github.com/buvis/agent-skills ls-files skills/brief-portfolio`
  lists it). The buvis command above would remove nothing.

- **Corrected owner deletion step (verify before running — owner action, out of
  gems scope):**

  ```sh
  # 1. Remove the skill from the repo that now tracks it:
  git -C ~/git/src/github.com/buvis/agent-skills rm -r skills/brief-portfolio
  git -C ~/git/src/github.com/buvis/agent-skills commit -m "refactor(skills): retire brief-portfolio — superseded by postup (gems PRD 00070)"
  git -C ~/git/src/github.com/buvis/agent-skills push

  # 2. Remove the now-dangling symlink from wherever it is provisioned
  #    (~/.agents/skills/brief-portfolio and ~/.claude/skills/brief-portfolio).
  #    If either symlink is itself tracked (e.g. by the buvis bare repo or a
  #    dotfiles manager), git rm it there rather than a plain rm.
  ```

  Re-run the buvis `ls-tree` and `agent-skills ls-files` checks at execution time
  before removing anything: this path has drifted twice already (layout move to
  `app/`/`scripts/`, then buvis→agent-skills), so confirm the current tracking
  rather than trusting either recorded command.

- **Fresh-history note (unchanged from discovery):** postup's trend/diff history
  restarts fresh on cutover — there is no legacy migration of the skill's
  `~/.local/share/agents/portfolio-brief/history.jsonl` into postup's
  `~/.local/share/postup/history.jsonl`. The "since last brief" diff is empty
  until postup has run at least twice.

### Gates (from the worktree, 2026-09-29)

Reported in the delivery message alongside the signed commit SHA.
