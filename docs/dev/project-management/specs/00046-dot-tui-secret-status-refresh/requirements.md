# dot TUI: refresh git-secret status so changed secrets show (issue #92)

<!-- requirements; migrated from PRD 00046 flat file -->

## Problem

In the dot TUI, a changed git-secret file does not appear in the unstaged pane until the user runs the CLI `dot status` first (issue #92, open since 2026-04-17). The CLI status path re-hides secrets before reading porcelain status — `cfg secret hide -m` then `cfg status --porcelain` (`src/tools/dot/commands/status/status.py:39-45`). The TUI's `GitOps.status()` skips that step entirely (`src/tools/dot/tui/git_ops.py:42-44`); it only hides at commit time (`git_ops.py:88-92`). So the encrypted `.secret` blob is stale until something else hides it, and the TUI's status reflects the stale blob — a correctness hole in a security-sensitive flow (a changed secret you never see, and therefore never commit).

## Solution

Mirror the CLI: at the top of `GitOps.status()`, when `git-secret` is available, run `cfg secret hide -m` before `cfg status --porcelain` — guarded exactly as the CLI does (skip when git-secret isn't installed; surface an error rather than silently proceeding).

## Requirements

### Must have
- `GitOps.status()` runs `cfg secret hide -m` (guarded by `is_command_available("git-secret")`) before reading porcelain status.
- On hide failure, the TUI surfaces the error (does not silently show stale status).
- Regression test: a modified secret file appears in the TUI's status entries without a prior CLI `dot status` call (mock the shell; assert `secret hide -m` is invoked before `status --porcelain`, and the modified secret shows up).

### Nice to have
- None.

## Success Criteria

- Issue #92 closed: the TUI unstaged pane shows changed secret files on first render.
- dot tests green.
