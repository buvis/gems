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

- **M1 Upstream wins**: for edits eligible under M2/M8/M9, `dot pull` no
  longer aborts on conflicting uncommitted edits. It saves them, resets
  those files to `HEAD`, then pulls. A successful pull ends with the
  upstream version in place for those files.
- **M2 Narrow scope**: only uncommitted tracked edits (staged or not) to
  files changed upstream since the common ancestor of `HEAD` and `@{u}`
  are eligible to be saved and reset. Differences caused solely by local
  commits do not count as incoming changes. Other local edits are left
  alone. Unpushed commits that conflict still fail the pull as they do today.
- **M3 Patch record**: one `git diff` patch per pull that saves anything, at
  `~/.local/share/dot/divergence/<timestamp>.patch`, covering every reset
  file. Its base is pre-pull `HEAD`, whose full commit ID must be included
  in the record. It must `git apply` cleanly onto that commit to reconstruct
  the saved local content.
- **M4 Save before destroy**: the patch is written with
  `pybase.filesystem.atomic_write` before any reset. If the write fails, pull
  aborts with nothing reset.
- **M5 Pull output**: every result after patch creation carries the patch
  path and one warning per file actually reset, including when a later
  reset, merge, submodule or secret-reveal step fails. CLI and TUI both
  render this recovery information alongside any error. A failed pull
  does not automatically restore edits from the patch.
- **M6 Status hint**: `dot status` and TUI status warn when any `*.patch`
  exists in the divergence dir (count plus dir path). Both use shared
  pending-patch logic. Pending = the file exists; the user deletes it once
  it has been handled. No other state.
- **M7 One implementation**: the logic lives in `DotGitService.pull` (the TUI
  calls the service directly, the CLI goes through `CommandPull`), so both
  get it.
- **M8 Mixed-state guard**: if any path selected for divergence reset has
  both staged and unstaged changes, pull aborts before any divergence
  reset, identifies the path and leaves its index and working content
  unchanged. This includes a working file restored to `HEAD` while its
  index still contains a different version.
- **M9 Host rescue priority**: when combined with intake 00088, host rescue
  preserves the original local content before any divergence reset of
  that path. Successfully rescued paths are excluded from divergence
  resets; upstream deletion must not replace the host-local source with
  `HEAD` content.

### Nice to have

- Patch header comment naming host and the upstream commit for additional
  context; the base commit ID is mandatory under M3.

### Out of scope

- Submodule edits wiped by `submodule foreach git reset --hard`.
- Revealed secret files overwritten by `secret reveal -f`.
- Resolving conflicts in unpushed local commits (still fail the pull).
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
  the merge, coordinated with 00088 host rescue; `CommandStatus.execute`
  and TUI status gain the pending-patch warning through shared logic.
- **Design starting point**: fetch, identify upstream changes since the
  common ancestor, and inspect index and worktree changes separately.
  Exclude successfully rescued host paths and reject mixed-state reset
  candidates before any divergence reset. Save eligible changes against
  pre-pull `HEAD`, including binary content and the full base commit ID,
  before resetting those paths and integrating upstream. Exact Git
  commands belong to design; a branch-tip diff is not the incoming set,
  and a worktree-to-HEAD diff alone is not a mixed-state check.

## Success Criteria

- Two-clone test: B edits `x` without committing, A changes `x` and pushes;
  B `dot pull` succeeds, `x` holds A's bytes, and a patch exists that turns
  B's pre-pull `HEAD` version of `x` into B's edit with `git apply`. The
  record includes that base's full commit ID.
- B also has an unrelated dirty file `y` -> `y` is unchanged after the pull,
  and not in the patch.
- B has an unpushed commit changing `y` and a further uncommitted edit to
  `y`, while upstream changes only `x` -> `y` is neither reset nor included
  in the patch, regardless of whether ordinary pull succeeds or fails.
- A selected file has staged content B and distinct working content C ->
  pull aborts before any divergence reset, names the file and preserves
  both versions. Repeat with C equal to `HEAD` to verify the staged version
  is still protected; other selected paths are not reset either.
- Combined with 00088: upstream deletes a manifest target while this host
  has local edits -> rescue preserves this host's original content in the
  host-local source, the target becomes the expected link, and divergence
  handling does not reset or replace the rescued content.
- No conflicting edits -> no patch written, output unchanged.
- Patch write fails (read-only dir) -> pull aborts, `x` still holds B's edit.
- A patch is saved and a later reset, merge, submodule or secret-reveal
  step fails -> the failure result retains the patch path and accurately
  identifies completed resets, and both CLI and TUI display this recovery
  information alongside the error. The patch remains available.
- `dot status` and TUI status with one patch present -> each shows one
  warning with count 1 and the directory; after deleting it and refreshing
  status -> neither shows a pending-patch warning.

## Risks

- **Collides with 00088 M9 (pull rescue)**: both add a fetch-before-merge
  step to `pull()`. Whichever lands second must preserve M9's host-rescue
  priority and run the combined acceptance case, not merely resolve code
  conflicts; resetting first would substitute `HEAD` bytes for host edits.
- **Losing data on a bad diff**: if the save misses a file but the reset hits
  it, the edit is gone. Mitigate: build the save and reset lists from the
  same set, and test that they match. Inspect index and worktree separately
  so mixed states cannot lose staged content through a combined diff.
- **No upstream (`@{u}` unset)**: skip detection and fall back to today's
  plain pull.
- **Binary files**: plain `git diff` omits binary content. Use `--binary`.

## Open Questions

- None remaining from this review. The patch base is pre-pull `HEAD`,
  identified by full commit ID, and pending-patch status is required in
  both CLI and TUI through shared logic.

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

### Review decisions (2026-10-12)

The user selected option 1 for all six findings in `review-discovery-doc`:

1. Refuse selected paths with both staged and unstaged changes before any
   divergence reset, preserving both versions (M8).
2. Define incoming paths by upstream changes since the common ancestor,
   excluding differences caused solely by local commits (M2).
3. Give 00088 host rescue priority, preserving original local content and
   excluding successfully rescued paths from divergence resets (M9).
4. Confirm pre-pull `HEAD` as the patch base and require its full commit ID
   in the record; this resolves the upstream-base wording in `idea.md` (M3).
5. Retain the patch path and accurate completed-reset warnings on every
   result after patch creation, including later failures (M5).
6. Show pending-patch count and directory in CLI and TUI status through
   shared logic (M6).
