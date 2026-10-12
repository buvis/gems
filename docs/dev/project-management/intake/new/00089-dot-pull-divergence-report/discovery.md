# Discovery: dot pull divergence report

## Classification

Depth: standard | Date: 2026-10-12

Source: `idea.md` beside this file.

## Problem

`dot pull` runs a plain `cfg pull`. When an uncommitted local edit touches a
file the incoming commits also change, git aborts with "would be
overwritten", and the user must discard the edit by hand, so it is lost along
with any fix worth sending upstream. Upstream should win, but the local edit
should be saved first in a form a maintainer can read or apply.

## Requirements

### Must have

- **M1 Upstream wins**: `dot pull` no longer aborts on conflicting
  uncommitted edits. It saves them, resets those files to `HEAD`, then pulls.
  The pull ends with the upstream version in place.
- **M2 Narrow scope**: only uncommitted tracked edits (staged or not) to
  files the incoming commits change (`HEAD..@{u}`) are saved and reset. Other
  local edits are left alone. Unpushed commits that conflict still fail the
  pull as they do today.
- **M3 Patch record**: one `git diff` patch per pull that saves anything, at
  `~/.local/share/dot/divergence/<timestamp>.patch`, covering every reset
  file. It must `git apply` cleanly onto the commit the edits were based on.
- **M4 Save before destroy**: the patch is written with
  `pybase.filesystem.atomic_write` before any reset. If the write fails, pull
  aborts with nothing reset.
- **M5 Pull output**: the result carries one warning per overwritten file
  plus the patch path. CLI and TUI both render it.
- **M6 Status hint**: `dot status` warns when any `*.patch` exists in the
  divergence dir (count plus dir path). Pending = the file exists; the user
  deletes it once it has been handled. No other state.
- **M7 One implementation**: the logic lives in `DotGitService.pull` (the TUI
  calls the service directly, the CLI goes through `CommandPull`), so both
  get it.

### Nice to have

- Patch header comment naming host, the base commit and the upstream commit,
  so a maintainer knows where it applies.

### Out of scope

- Submodule edits wiped by `submodule foreach git reset --hard`.
- Revealed secret files overwritten by `secret reveal -f`.
- Unpushed local commits (still fail the pull).
- Sending the patch anywhere (issue, PR, pushed branch). That stays manual.
- A `dot divergence` verb to list, show or delete patches.
- Raw `git pull` (bypasses dot, unchanged).

## Constraints

- No new dependencies.
- Divergence dir sits under `~/.local`, never tracked (glean `check-staged`
  already blocks `.local/`).
- No `print`/`click.echo`; output goes through `CommandResult`.
- Atomic write for the patch (AGENTS.md invariant).

## Codebase Context

- **Relevant code**: `src/tools/dot/git/service.py:132` `DotGitService.pull`
  (runs `cfg pull`, then submodule reset/init/update, then secret reveal);
  `src/tools/dot/commands/pull/pull.py` (thin `CommandPull` wrapper);
  `src/tools/dot/commands/status/status.py` (`CommandStatus`, builds
  `warnings`/`info`); `src/tools/dot/tui/screens/main.py:263`
  `action_pull` (calls `_git_ops.pull` directly).
- **Conventions**: git via the `cfg` alias through `ShellAdapter.exe`
  returning `(err, out)`; `CommandResult(warnings=...)`; tests mock the
  shell.
- **Integration points**: `pull()` gains a fetch-detect-save-reset step before
  the merge; `CommandStatus.execute` gains the pending-patch warning.
- **Likely git shape**: `cfg fetch`; incoming = `cfg diff --name-only
  HEAD @{u}`; dirty = `cfg diff --name-only HEAD`; save = `cfg diff HEAD --
  <files>`; reset = `cfg checkout HEAD -- <files>`; then `cfg pull`.

## Success Criteria

- Two-clone test: B edits `x` without committing, A changes `x` and pushes;
  B `dot pull` succeeds, `x` holds A's bytes, and a patch exists that turns
  A's base `x` into B's edit with `git apply`.
- B also has an unrelated dirty file `y` -> `y` is unchanged after the pull,
  and not in the patch.
- No conflicting edits -> no patch written, output unchanged.
- Patch write fails (read-only dir) -> pull aborts, `x` still holds B's edit.
- `dot status` with one patch present -> one warning naming the dir;
  after deleting it -> no warning.

## Risks

- **Collides with 00088 M9 (pull rescue)**: both add a fetch-before-merge
  step to `pull()`. Whichever lands second rebases onto the other's shape.
- **Losing data on a bad diff**: if the save misses a file but the reset hits
  it, the edit is gone. Mitigate: build the save and reset lists from the
  same set, and test that they match.
- **No upstream (`@{u}` unset)**: skip detection and fall back to today's
  plain pull.
- **Binary files**: plain `git diff` omits binary content. Use `--binary`.

## Open Questions

- R2 in `idea.md` says "diff against the upstream version". The patch here
  diffs against the local base (`HEAD`), because that is what applies
  cleanly and shows only the local change. create-prd should confirm.
- Does the TUI show the status hint (M6)? Its main screen uses
  `has_uncommitted_changes`, not `CommandStatus`.

## Discovery Log

### Q1: Which overwrite should the record cover?
**Context**: `cfg pull` aborts today on conflicting tracked edits; silent loss
happens only in `submodule foreach git reset --hard` and `secret reveal -f`.
**Answer**: Tracked files only. Pull changes so tracked-file conflicts end
with upstream winning (record, then overwrite) instead of aborting.
Submodules and secrets stay as they are.

### Q2: Which local changes count as diverged?
**Answer**: Only uncommitted edits to files the incoming commits touch.
Unrelated local edits survive. Unpushed commits that conflict still fail the
pull (unchanged).

### Q3: Where and in what form is the record saved?
**Answer**: One `git diff` patch per pull at
`~/.local/share/dot/divergence/<timestamp>.patch`. Readable and
`git apply`-able; never tracked.

### Q4: How does dot surface the record?
**Answer**: Pull's result lists the overwritten files and the patch path as a
warning (CLI and TUI both render it). `dot status` also notes when pending
patches exist. Sending to the maintainer stays manual.

### Q5: When does a patch stop counting as pending?
**Answer**: Until the file is deleted. Any `*.patch` in the dir is pending;
no extra state.

### Inferred (not asked)
- Logic placement: `DotGitService.pull`, because the TUI bypasses
  `CommandPull` (M7).
- Save-before-reset with atomic write and abort on failure: data-loss guard
  required by AGENTS.md invariants (M4).
- `--binary` diff and the no-upstream fallback: edge cases from the git
  shape, not user choices.
