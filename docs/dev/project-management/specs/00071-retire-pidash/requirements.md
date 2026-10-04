# Retire the pidash tool from buvis-gems

<!-- requirements; migrated from PRD 00071 flat file -->

## Problem

pidash (`src/tools/pidash/`, a Textual TUI) is dead code. It types autopilot's
`prd` field as a required object while the live schema uses a bare string, so
every parse fails and the tool renders "no active PRD cycle" no matter what the
autopilot is doing. Its successor is `tracon`, which lives in the buvis home
repo at `~/.claude/skills/run-autopilot/scripts/tracon/`, next to the state
schema it reads — that proximity is what removes the cross-repo drift that
killed pidash. pidash is already inert on the operator machine: its hooks are
unregistered and deleted, `~/.pidash/` is purged (1,382 files logged before
removal), and the autopilot docs are scrubbed. The gems repo still carries the
tool, its tests, its docs page, and its packaging extra, so every release ships
and every `rg pidash` hit points at code nobody can run.

## Solution

Delete pidash from gems and nothing else. No replacement code lands here:
tracon is presentation-only and out of gems scope, so this PRD is pure removal
plus the CHANGELOG entry that names where the function went. Removal spans six
surfaces that are easy to half-finish — the package, its tests, the console
script, the `pidash` optional-dependency extra (including its membership in
`all`), the docs page and its toctree entry, and the pytest marker — so each is
its own acceptance criterion rather than one "the directory is gone" check.

## Requirements

### Must have

- Premise re-check at execution: `src/tools/pidash/` still exists. If it is
  already gone, skip and report; never force.
- `src/tools/pidash/` and `tests/tools/pidash/` removed.
- `pidash` console script removed from `[project.scripts]`, and the wheel
  package entry removed from the hatch package list.
- `pidash` optional-dependency extra removed from `[project.optional-dependencies]`,
  and removed from the `all` extra.
- `pidash` pytest marker removed from the `markers` list in `pyproject.toml`.
- `docs/source/tools/pidash.rst` removed and its toctree entry unlinked.
- CHANGELOG entry under Removed naming `tracon` (buvis home repo) as the
  successor.
- No orphaned references: `rg pidash` is clean outside CHANGELOG history and
  `dev/local/prds/hold/`.

### Nice to have

- Close pidash issues #111-#114 as superseded (their substance is now moot: the
  hooks they described no longer exist on the machine or in the repo).

## Success Criteria

- `rg pidash src/ tests/ docs/ pyproject.toml` is empty.
- `uv run pytest`, `uv run mypy src/lib/ src/tools/`, and the docs build are all green after removal.
- Installing any remaining extra (`uv sync --all-extras`) succeeds with no reference to a `pidash` extra.
- CHANGELOG names `tracon` as where the function went, so a reader of the release notes is not left looking for it in gems.
