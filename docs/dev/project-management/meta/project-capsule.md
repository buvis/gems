# Project Capsule: buvis-gems

Generated: 2026-10-24

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
- dot's host-filter surface lives in `src/tools/dot/git/filter_driver.py` as `FilterDriverMixin` (split out of `service.py` at 861 lines, over the 800 max); `_literal` moved there and `service.py` imports it from there.
- sysup capabilities yield `StepResult`; config validates their `inputs` against `with:` and the runner owns dry-run, error conversion, command stamping, and run-log markers. Registering a capability therefore exposes it through the existing shared runner without another interface implementation.

## Active Work

### Batch 202610261200
- [x] `00108-sysup-uv-tool-python-upgrade-in-place-v1.md` (1 cycle)

Observations: Fast-track lane. `uv tool upgrade --python` now moves customized receipts in place. One VERIFY left open by the doubt lens (Eve): whether `uv tool upgrade --python` can delete a tool's receipt before a failed sync completes, leaving rollback without a receipt to restore, and whether the upgraded receipt records the new interpreter — unverified against uv 0.13.5 behavior; also open: add a `future=false` + pinned-customized case to `test_moves_customized_receipts_in_place` and fold `test_accepts_plain_receipts_with_harmless_metadata` into it. Both VERIFY items were later confirmed against uv 0.13.5 and fixed in 210e674c (receipt restore before rollback; skip tools whose `pyvenv.cfg` minor is already the target). Batch drained - both `wip/` and `backlog/` are empty.

### Batch 202610242315
- [x] `00105-sysup-uv-tool-python-pin-v1.md` (1 cycle)

Observations: New `UvToolPython` pins supported plain unpinned/older installs before uv upgrades (order35 before40); preserves newer pins, visibly skips customized/unreadable receipts, and reports rollback failures honestly. Full suite green at 63e0d4ef (5665 passed, 0 failed, 16 skipped) under isolated writable state/config and with the loop launcher's GIT_AUTHOR_NAME/GIT_COMMITTER_NAME dropped (otherwise 2 unrelated klyreon identity tests fail - known env noise, not a regression). One HIGH deferred to batch-end: `engram`'s editable install stays unpinned/red on this host (triage stub `00106-triage-engram-gets-skipped-with-success-false-o-v1.md` minted). Batch drained - both `wip/` and `backlog/` are empty.

## Related context
Topic: `master sysup uv-tool-python: pin freestanding uv tools to the global python minor`. Repo/portfolio queries, repo index refresh, and review harvest were attempted but interrupted after waiting without results: the embedding endpoint `http://127.0.0.1:8083/v1` refused connections and engram kept retrying startup. No related-hit claim is possible. Portfolio status completed (exit 1): memory 192/stale 24/dead 1; PRD 9156/dead 3063; discovery 531/dead 50; transcripts 17713/dead 17604; code 57876/stale 76/dead 21, skipped 5686; findings 34368; decisions 25/stale 1. Directly loaded precedent: `src/tools/sysup/capabilities/pipx_python.py` and its registry/default wiring.

## GitHub State
- 0 open issues. Six open Renovate PRs: #249 patch updates, #248 minor updates, #245 pillow v13, #231 lock maintenance, #220 SvelteKit v3, #219 adapter-static v4. The two Svelte majors still report artifact-update failures. No feature PR overlaps the sysup capability work.
- At master `db6b1b43`, the 2026-10-24 Test run is queued; Deploy Documentation succeeded. Latest completed master Test succeeded on 2026-10-18. Historical 2026-10-13 failure reports `Lib tests failed` because its lib job was `abandoned`, not a confirmed current regression.
- Latest release is `gems-v0.14.2` (2026-10-17), with 96 unreleased master commits. Catchup starts on master, so feature-branch diff/issue extraction is inapplicable; worktree changes are autopilot telemetry and the PRD's backlog-to-wip move.

## Project Health
- A `lib` failure skips the `tools` matrix. Local tests need writable XDG_STATE_HOME and a high-priority empty postup roots config to avoid host lock permissions/operator portfolio configuration; PRD00105 build evidence records this isolation. `BUVIS_SKIP_FRONTEND=1` + scratch `CARGO_HOME` needed for `uv sync`/`uv run` under the Seatbelt profile.
