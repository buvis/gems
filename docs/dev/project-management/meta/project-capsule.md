# Project Capsule: buvis-gems

Generated: 2026-10-12

## Key Invariants
- Commands return `CommandResult`; only `cli.py`/adapters render via `console`. No print/click.echo/logging.
- Persist with `pybase.filesystem.atomic_write`, never bare `write_text`.
- dot: one action, one implementation across CLI/TUI (`DotGitService` is the seam, PRD 00053). TUI must call the same command classes as CLI.
- Lazy imports inside Click handlers.
- Every CLI change updates `docs/source/tools/<tool>.rst` and `README.md`.

## Architecture Decisions
- Single PyPI package `buvis-gems`; tools are top-level packages in the wheel.
- dot works against a bare dotfiles repo (`cfg` wrapper, work-tree `$HOME`); `dotfiles_root` is resolved in `cli.py` (`DOTFILES_ROOT` env).

## Component Boundaries
- `src/tools/dot/`: `cli.py` -> `commands/<name>/` -> `git/service.py` (`DotGitService`); TUI (`tui/app.py`, `tui/screens/main.py`, `tui/widgets/status_bar.py`) drives the same commands.

## Active Work
- Autopilot batch 202610121200 on master. PRDs: 00088 (wip, dot host-links materialize), 00090 (backlog, localize + pull rescue), 00091 (backlog, self-heal + setup).
- Intake: 00088 and 00089 (pull divergence report) discovery docs carry uncommitted edits.
- Working tree also has uncommitted postup frontend build churn (not this batch's work).

## Related context
engram unavailable (not on PATH); no related-context query run. Topic would have been: "dot host links: manifest, materialize, hooks, link status".

## GitHub State
- 0 open issues. Open PRs: #231 lock-file maintenance (automerge), #220 @sveltejs/kit v3 and #219 adapter-static v4 (both with Renovate artifact-update failures, do not merge as-is).
- Latest release gems-v0.14.0 (2026-10-12), 2 unreleased commits.
- Remote branch `fix/config-merge-aliasing` active (4h old).

## Project Health
- Test on master queued at catchup time; older failures (2026-09-28, 2026-08-31) were Test runs, and an old docs deploy failure (gh-pages push race, 2026-10-04) has since succeeded.
- See memory: a `lib` failure skips the `tools` matrix; 3 known env-noise local test failures.
