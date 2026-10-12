---
design: run
default_model: opus
model_tier_rationale: destructive blast radius - moves user files in $HOME and gates a merge that would otherwise delete them
---

# dot host links: localize and pull rescue

Source: `docs/dev/project-management/intake/new/00088-dot-materialize-host-config/discovery.md`
(PRD B+C of 3, M8 + M9). Depends on 00088 (manifest, `reconcile_links`,
`CommandMaterialize`). Shipped together so localize never exists without the
pull-side deletion guard.

## Overview

### Problem Statement
Turning a tracked file into a host-specific one means: move it to a host-local
source, add a manifest line, link it, untrack it. Done by hand on host A, the
untrack commit then deletes host B's real file on pull. This PRD adds
`dot localize` and makes `dot pull` rescue such files before merging.

### Target Users
The solo dotfiles owner with several hosts sharing one dotfiles repo.

### Success Metrics
- `tests/tools/dot/test_localize.py`, `test_hostlinks_rescue.py`,
  `test_pull.py`, `test_pull_two_hosts.py`, `test_rescue_modal.py` pass.
- Two-host test: A localizes a tracked file and pushes; B `dot pull` -> B's
  original bytes sit at the source, the target is a link to them.
- Collision (target and source both present, different bytes): each choice
  does what it says and loses no bytes; cancel and noninteractive pulls leave
  both paths unchanged and do not merge.

## Functional Decomposition

### Capability: Localize

#### Feature: `dot localize <path> [--to <source>]`
- **Description**: Make one file or dir host-specific.
- **Inputs**: `path` (`$HOME`-relative, or absolute under the dotfiles root and
  then relativized); `--to` source, default `.local/<path>`.
- **Outputs**: `CommandResult` with info lines `moved <path> to <source>`,
  `linked <path>`, `untracked <path>` (only when it was tracked),
  `staged .config/buvis/host-links`.
- **Behavior**: validate the pair with the 00088 manifest rules (same reason
  strings). Refuse, changing nothing, when: target missing; target is a link;
  source exists or is a link; target already listed in the manifest; target or
  any file under it is listed by `DotGitService.list_secrets()` (error
  `<path> is a git-secret file; localize refused`). Then, in order (untrack
  runs first, while the path is still a real file or dir, never through a
  link):
  1. When `DotGitService.ls_files(target)` is non-empty:
     `DotGitService.untrack(target)` = `cfg rm -r --cached --quiet -- <path>`
     (index only, disk untouched). Failure -> return
     `untrack failed: <err>`, nothing changed.
  2. `source.parent.mkdir(parents=True, exist_ok=True)`, `shutil.move(t, s)`.
  3. Create the link for this one entry with the 00088 link-creation code.
  4. `append_entry(root, HostLink(target, source))`: atomic rewrite of the
     manifest with `<target> => <source>\n` appended (adds a newline first
     when the file lacks a trailing one; creates the file when missing).
  5. `DotGitService.stage(MANIFEST_PATH)`.
  Rollback when step 2, 3 or 4 fails, in reverse: remove the link if
  created, move `s` back to `t` if moved, and when step 1 ran restore the
  index with `DotGitService.unstage(target)`; then return the error. A step 5
  failure keeps everything and returns `stage failed: <err>; run 'dot add
  .config/buvis/host-links'`.

### Capability: Pull rescue

#### Feature: Plan rescue
- **Description**: Find incoming deletions of manifest targets, without
  changing anything.
- **Inputs**: dotfiles root, `DotGitService` after `fetch()`.
- **Outputs**: `RescuePlan(moves, duplicates, collisions, skipped)`; the first
  three are `list[HostLink]`, `skipped` is `str | None`.
- **Behavior**: `has_upstream()` false -> `skipped = "pull rescue skipped: no
  upstream branch"`. Incoming manifest = `parse_manifest(show_upstream_file(
  MANIFEST_PATH) or "")`. Deleted = `upstream_deleted_paths()`
  (`cfg diff --name-only --no-renames -z --diff-filter=D HEAD...@{u}`, split
  on NUL; `--no-renames` stops a delete pairing with an add as a rename, `-z`
  stops path quoting). An entry is affected
  when a deleted path equals its target or starts with `target + "/"`. For an
  affected entry: target missing or already a link -> ignore; source missing
  -> `moves`; both regular files with `filecmp.cmp(t, s, shallow=False)` ->
  `duplicates`; anything else (different bytes, any dir) -> `collisions`.

#### Feature: Apply rescue
- **Inputs**: plan, `resolutions: dict[str, Resolution]` keyed by target.
- **Outputs**: `CommandResult`; info lines `rescued <target> to <source>`,
  `kept <source>, moved <target> to <backup>`,
  `kept <target> as <source>, moved old source to <backup>`.
- **Behavior**: `Resolution` is a stdlib enum.StrEnum (3.11+): `KEEP_SOURCE = "keep-source"`,
  `KEEP_TARGET = "keep-target"`, `CANCEL = "cancel"`. Any collision without a
  resolution, or any `CANCEL` -> failure
  `pull stopped: unresolved host-link collision(s): <t1>, <t2>`, no change.
  Backup path = `<source>.dot-<UTC %Y%m%dT%H%M%SZ>`; if one already exists ->
  failure before any change. Then: moves -> `shutil.move(t, s)`; duplicates
  -> unlink `t` (source holds the same bytes); `KEEP_SOURCE` -> move `t` to
  backup; `KEEP_TARGET` -> move `s` to backup, then `t` to `s`. Nothing is
  ever deleted except a byte-identical duplicate.

#### Feature: `dot pull` with rescue
- **Behavior**: `CommandPull(shell, dotfiles_root, *, git_service=None)`.
  `plan()` runs `fetch()` (error -> plan with `error="Fetch failed: <err>"`)
  then plans. `execute(plan=None, resolutions=None, passphrase=None)`: plans
  when `plan` is None; plan error -> failure; apply rescue (failure -> return
  it, no merge); `DotGitService.pull(passphrase=passphrase)`; on pull failure
  after any rescue move append `rescued files are at: <sources>` to the error;
  then `CommandMaterialize(..., install_hooks=False)` and merge its info and
  warnings, plus `skipped`, into the result.
  CLI: when `plan.collisions` and `sys.stdin.isatty()`, for each collision
  print `<target> and <source> both exist and differ` via `console.warning`
  and ask `console.choose("Resolve", ["keep-source", "keep-target",
  "cancel"], default="cancel")`; non-TTY -> no prompt, `execute` reports.
  TUI `P`: `CommandPull(..., git_service=self._git_ops)`, plan, then one
  `RescueCollisionModal` per collision (keys `s` keep source, `t` keep target,
  `escape` cancel, dismiss value a `Resolution`); a cancel shows
  `Pull cancelled; nothing changed` and stops; then the existing passphrase
  flow, then `execute`.

## Structural Decomposition

### Repository Structure

```
src/lib/buvis/pybase/adapters/console/console.py  # + choose()
src/tools/dot/
├── hostlinks/manifest.py       # + append_entry
├── hostlinks/rescue.py         # plan + apply rescue
├── commands/localize/{__init__,localize}.py
├── commands/pull/pull.py       # plan/execute with rescue
├── git/service.py              # + fetch, has_upstream, show_upstream_file,
│                               #   upstream_deleted_paths, untrack
├── tui/widgets/rescue_modal.py
├── tui/screens/main.py         # action_pull via CommandPull
└── cli.py                      # localize; pull prompts
```

### Module: hostlinks.rescue
- **Maps to capability**: Pull rescue
- **Responsibility**: Decide and perform the pre-merge moves.
- **Exports**: `Resolution`, `RescuePlan`, `plan_rescue(root, git_service)`,
  `apply_rescue(root, plan, resolutions)`.
- New symbols: `rescue`, `Resolution`, `RescuePlan`, `plan_rescue`, `apply_rescue`, `KEEP_SOURCE`, `KEEP_TARGET`, `CANCEL`

### Module: commands and adapters
- **Maps to capability**: Localize, `dot pull` with rescue
- **Exports**: `CommandLocalize(shell, dotfiles_root, path, source=None)`,
  `CommandPull.plan()`, `append_entry(root, link)`, `ConsoleAdapter.choose(question, choices, default)`
  (rich `Prompt.ask(question, choices=choices, default=default)`),
  `RescueCollisionModal`, `DotGitService.fetch/has_upstream/show_upstream_file/upstream_deleted_paths/untrack`.
- New symbols: `reconcile_links`, `CommandMaterialize`, `MANIFEST_PATH`, `HostLink`, `parse_manifest` (created by prerequisite PRD 00088, must exist before this PRD starts)
- New symbols: `CommandLocalize`, `localize`, `append_entry`, `choose`, `RescueCollisionModal`, `rescue_modal`, `fetch`, `has_upstream`, `show_upstream_file`, `upstream_deleted_paths`, `untrack`, `git_service`

## Dependency Graph

### Foundation Layer (Phase 0)
- **git.service additions, manifest.append_entry, console.choose**: depend only
  on 00088 (`MANIFEST_PATH`, `HostLink`, `parse_manifest`).

### Core Layer (Phase 1)
- **hostlinks.rescue**: depends on [git.service additions, manifest]
- **commands.localize**: depends on [manifest.append_entry, git.service.untrack, 00088 linker]

### Integration Layer (Phase 2)
- **commands.pull, cli, tui**: depend on [hostlinks.rescue, console.choose, 00088 CommandMaterialize]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Primitives.

**Tasks**:
- [ ] Service methods `fetch()` (`cfg fetch`, returns err text, "" on
  success), `has_upstream()` (`cfg rev-parse --verify --quiet @{u}`),
  `show_upstream_file(path)` (`cfg show @{u}:<path>` shell-quoted, `None` on
  error), `upstream_deleted_paths()`, `untrack(path)` (no deps) - Acceptance:
  new tests in `tests/tools/dot/test_git_service.py` assert the exact command
  strings and error handling.
- [ ] `append_entry` and `console.choose` (no deps) - Acceptance: new tests in
  `tests/tools/dot/test_hostlinks_manifest.py` (append to missing file, to
  file without trailing newline, round-trips through `parse_manifest`) and
  `tests/lib/pybase/adapters/test_console_adapter.py` (`choose` passes choices and default
  to `Prompt.ask`) pass.

**Exit Criteria**: new primitive tests green.

### Phase 1: Core
**Goal**: Rescue logic and `dot localize`.

**Tasks**:
- [ ] `hostlinks/rescue.py` per Plan/Apply rescue (depends on: Phase 0) -
  Acceptance: `uv run pytest tests/tools/dot/test_hostlinks_rescue.py` passes;
  covers move, duplicate, dir collision, file collision with each
  resolution (bytes of both originals present afterwards), cancel and
  missing resolution change nothing, existing backup path fails before any
  change, no upstream -> `skipped` set.
- [ ] `CommandLocalize` + `dot localize` CLI (depends on: Phase 0) -
  Acceptance: `uv run pytest tests/tools/dot/test_localize.py` passes; covers
  file and dir, default and `--to` source, each refusal leaves disk and
  manifest unchanged, untrack failure changes nothing, link and manifest
  failures roll back move and index (`unstage` called), stage failure names
  `dot add`. One real-git case (real `ShellAdapter`, tmp bare repo): localize
  a tracked dir -> `ls_files` of it is empty afterwards and its files sit at
  the source.

**Exit Criteria**: rescue and localize tests green.

### Phase 2: Integration
**Goal**: Rescue wired into `dot pull` for CLI and TUI.

**Tasks**:
- [ ] `CommandPull.plan/execute`, CLI prompts, TUI modal and `action_pull`
  (depends on: Phase 1) - Premise: exactly the 3 tests in
  `TestCommandPullExecute` and 1 `test_pull_calls_git_ops` mock the service
  without fetch stubs; re-check with
  `rg -c "def test_" tests/tools/dot/test_pull.py` (expect 6) before editing,
  and if the count differs stop and report instead of rewriting tests. Those
  4 tests gain only `fetch.return_value = ""` and
  `has_upstream.return_value = False` stubs; their assertions stay.
  Acceptance: `uv run pytest tests/tools/dot/test_pull.py tests/tools/dot/test_rescue_modal.py tests/tools/dot/test_tui_app.py`
  passes, including: noninteractive collision -> failure, both paths
  unchanged, `pull` not called; TUI cancel -> `pull` not called.
- [ ] Two-host real-git test `tests/tools/dot/test_pull_two_hosts.py` (depends
  on: previous task): tmp bare origin, hosts A and B as bare clones with
  work-trees, git identity set via `monkeypatch.setenv`, real
  `ShellAdapter`. A localizes a tracked file, commits, pushes; B (with local
  uncommitted bytes in that file) runs `CommandPull(...).execute()` ->
  B's bytes at the source, target is a link to it. Second case: B also has a
  different source file -> noninteractive failure, B's HEAD unchanged.
  Acceptance: `uv run pytest tests/tools/dot/test_pull_two_hosts.py` passes.
- [ ] Docs: `docs/source/tools/dot.rst` and `README.md` cover `dot localize`,
  pull rescue, the collision choices, and that raw `git pull` bypasses the
  rescue (depends on: previous task) - Acceptance:
  `rg -n "dot localize" docs/source/tools/dot.rst README.md` finds both.

**Exit Criteria**: `uv run pytest -m dot` and `uv run mypy src/tools/dot src/lib` pass.

## Test Strategy

### Critical Scenarios
- **Happy path**: two-host localize then pull -> B's bytes rescued and linked.
- **Edge case**: identical target and source -> target removed, no prompt.
- **Edge case**: dir target collision -> always a prompt, never auto-merged.
- **Error case**: noninteractive collision -> report, no move, no merge.
- **Error case**: fetch fails -> failure, nothing moved.

## Risks

- **Raw `git pull` bypasses rescue**: documented; git has no pre-pull hook.
- **00089 also changes `dot pull`**: both add a fetch before `cfg pull`.
  Whichever lands second keeps one `fetch()` call and runs both pre-merge
  steps; 00089's divergence save must run after rescue moves.
- **Window between fetch and `cfg pull`**: `cfg pull` re-fetches, so a commit
  pushed in that gap is merged unplanned. Git still refuses to delete a
  locally modified file, so bytes survive; accepted.
- **Glean settling (M13)**: after this ships, localize
  `~/.config/gita/repos.csv` on this host and add `~/.local` to glean
  link_roots by hand; not an autopilot task (config outside gems).
