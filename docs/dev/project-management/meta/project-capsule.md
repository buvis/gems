# Project Capsule: buvis-gems

Generated: 2026-10-19

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

## Active Work

### Batch 202610121200
- [x] 00088-dot-host-links-materialize-v1 (1 cycle)
- [x] 00098-sysup-run-observability-v1 (2 cycles)
- [ ] 00099-dot-shared-config-host-fragments-v1 (wip, this session, 2/6 tasks done, resuming at task 3 `CommandShare`) — Git clean/smudge filter for shared dotfiles with per-host `@HOME@` token substitution; new `src/tools/dot/hostfilter.py`, `CommandShare`, `DotGitService._ensure_filter_driver`/`renormalize`. Task 2 landed at 28d1e606. Carried obligation into task 3: a test that a `target` whose `capture_index_entry` returns None (conflicted, or an unreadable `ls-files`) is refused by check 12 and never reaches `restore_index_entry(target, None)`, whose None branch runs `rm --cached`. Design-doc corrections now authoritative over the original task text: `--cacheinfo` takes a PATHNAME (not a `:(literal)` pathspec), `--add` is REQUIRED (git exits 128 otherwise), and `capture_index_entry` captures only a stage-0 record.
- Backlog is empty: 00099 is the last PRD of this batch.

## Related context
Topic queried: "dot shared config host fragments". Repo hits: the wip PRD itself (`prds/wip/00099-...md:6-9` 0.0328, `:49-54` 0.0161), then `prds/done/00088-dot-host-links-materialize-v1.md:7-11` 0.0159 and `prds/done/00091-dot-host-links-setup-v1.md:52-74` 0.0156 (the two prior dot host-links PRDs, the nearest precedent for this filter work) and `reviews/00091-...-review-2.md:16` 0.0154. Portfolio adds only `claude-aegis/.../00011-extract-shared-shell-parser-v1.md` 0.0159 (name collision on "shared", not relevant). No precedent doc beyond the 00099 design doc and the 00088/00091 reviews. Staleness (`engram status --scope portfolio`, exit 1): memory 192/stale 24/dead 1, code 57261/stale 81/dead 21 (5645 skipped), transcripts 17713 with 17604 dead, prd 9000 with 3179 dead — the index carries a lot of dead rows, so absence of a hit is weak evidence. Harvest gap: 17 review/meta files under `reviews/` failed to harvest (`missing frontmatter`), including every `backlog-review-*`, the evolution assessment, and the per-PRD `-audit.md` renders.

## GitHub State
- 0 open issues. Open PRs (all renovate, none for this PRD's scope): #245 pillow v13, #231 lock-file maintenance (automerge armed, and its branch's Test run is RED as of 2026-10-19 — it will not merge green), #220 @sveltejs/kit v3 and #219 adapter-static v4 (both with artifact-update failures, do not merge as-is). CI on master green (2026-10-18, latest Test + Deploy Documentation both success); older master failures (10-04 through 10-13) are historical — the 10-13 one was a cancelled (`abandoned`) lib job, not a code failure. 9 unreleased commits on master since `gems-v0.14.2` (2026-10-17).

## Project Health
- See memory: a `lib` failure skips the `tools` matrix; 3 known env-noise local test failures (klyreon GIT_AUTHOR_NAME, postup gh call). `BUVIS_SKIP_FRONTEND=1` + scratch `CARGO_HOME` needed for `uv sync`/`uv run` under the Seatbelt profile.
