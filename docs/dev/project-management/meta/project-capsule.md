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
### Batch 202610121200
- [x] 00088-dot-host-links-materialize-v1 (1 cycle)
- [ ] 00090-dot-host-links-localize-pull-rescue-v1
- [ ] 00091-dot-host-links-setup-v1
- [ ] 00094-updater-installer-index-parity-v1
- [ ] 00095-dot-pull-divergence-report-v1 (renumbered from 00089 on 2026-10-12: depends on 00090; 00092/00093 are intake numbers)

Observations: codex reviewer unhealthy under Seatbelt (sandbox_apply EPERM); qwen excluded on memory pressure for 3 tasks. Working tree has uncommitted postup frontend build churn (not this batch's work). Deferred: TUI status message overwritten by diff re-render (pre-existing, screens/main.py).

## Related context
engram unavailable (not on PATH); no related-context query run. Topic would have been: "dot host links: manifest, materialize, hooks, link status".

## GitHub State
- 0 open issues. Open PRs: #231 lock-file maintenance (automerge), #220 @sveltejs/kit v3 and #219 adapter-static v4 (both with Renovate artifact-update failures, do not merge as-is).
- Latest release gems-v0.14.0 (2026-10-12), 2 unreleased commits.
- Remote branch `fix/config-merge-aliasing` active (4h old).

## Project Health
- Test on master queued at catchup time; older failures (2026-09-28, 2026-08-31) were Test runs, and an old docs deploy failure (gh-pages push race, 2026-10-04) has since succeeded.
- See memory: a `lib` failure skips the `tools` matrix; 3 known env-noise local test failures.
