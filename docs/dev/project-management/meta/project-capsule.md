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
### New batch (master, 2026-10-18)
- [ ] 00098-sysup-run-observability-v1 (selected; default_model: opus)
- 00099 (dot shared config placeholders) also in backlog.
- Prior batch 202610121200 (00088-00095, dot host-links set) is not in `wip/` anymore — presumed closed/drained; this is a fresh batch.

## Related context
engram unavailable (not on PATH); no related-context query run. Topic: "master: sysup run observability".

## GitHub State
- 0 open issues. Open PRs (all renovate, none for this PRD's scope): #245 pillow v13, #231 lock-file maintenance (automerge), #220 @sveltejs/kit v3 and #219 adapter-static v4 (both with artifact-update failures, do not merge as-is).

## Project Health
- See memory: a `lib` failure skips the `tools` matrix; 3 known env-noise local test failures (klyreon GIT_AUTHOR_NAME, postup gh call). `BUVIS_SKIP_FRONTEND=1` + scratch `CARGO_HOME` needed for `uv sync`/`uv run` under the Seatbelt profile.
