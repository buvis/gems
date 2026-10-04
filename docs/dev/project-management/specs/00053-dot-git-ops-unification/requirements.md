# dot: unify the git command layer behind one service

<!-- requirements; migrated from PRD 00053 flat file -->

## Overview

### Problem Statement
dot has its git logic implemented **three times**. The CLI drives `dot/commands/{status,add,unstage,commit,push,pull,rm,delete}/`; the TUI drives a parallel `GitOps` class with 15 public methods that shadow those commands (`src/tools/dot/tui/git_ops.py`); and a third mini-layer lives under `dot/tui/commands/{browse,secrets}.py`. The duplication is not cosmetic — the git-secret-hide-then-commit sequence is logic-identical in `git_ops.py:88-97` and `commands/commit/commit.py:28-45`, and the submodule reset/init/update + secret-reveal pull sequence is duplicated in `git_ops.py:108-133` and `commands/pull/pull.py:34-53`. This is where dot's bug cluster lives (dot carries 46 fixes across 158 commits, 14.2 fixes/kloc — the highest in the repo), because every git-policy fix must land in two places and the paths drift. Issue #92 (fixed narrowly in 00046) is one symptom.

### Target Users
Bob (dot CLI + TUI daily) and dot maintainers — every future git-behavior change should be made once.

### Success Metrics
- One git-ops implementation; CLI and TUI both consume it.
- 0 duplicated git-policy sequences (commit-with-secret-hide, pull-with-submodules) across `commands/` and `tui/`.
- dot test suite covers the service directly (not through the Textual widget).

## Functional Decomposition

### Capability: Shared git operations
One non-interactive service owns every git verb dot performs; interfaces are thin.

#### Feature: DotGitService
- **Description**: status/add/unstage/stage/commit/push/pull/rm/delete as methods returning `CommandResult` (queries return their data), with git-secret and submodule policy in one place.
- **Inputs**: injected `ShellAdapter` + `dotfiles_root` (constructor param, not `os.environ` mutation).
- **Outputs**: `CommandResult` for mutations; typed data for queries (`status()` → file entries).
- **Behavior**: the current `GitOps` behavior is the better-shaped base (it already takes `dotfiles_root` and returns `CommandResult`); fold the CLI command classes' behavior into it, including the 00045 rm-safety and 00046 secret-status fixes.
