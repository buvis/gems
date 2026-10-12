# dot: record local divergence before pull overwrites it

Status: processed, specced as PRD 00095 (renumbered from 00089). Recorded 2026-10-12.

## Problem

When `dot pull` finds local changes that the pull would overwrite, the local
changes must lose: upstream wins in the end. That part is settled. But today
the local edits just vanish, and with them any fix or tweak worth sending
back upstream.

## Idea (from the user)

Before overwriting, take note of everything that diverged locally, so it can
be reported to the upstream maintainer for possible inclusion.

## Requirements

1. **R1 Upstream wins**: the pull still ends with the upstream version in
   place. The record never blocks or undoes the overwrite.
2. **R2 Full record**: every file that diverged, with enough to rebuild the
   change (path plus diff against the upstream version).
3. **R3 Reportable**: the record is in a form a maintainer can read or apply.

## Open questions

- Where the record lives (file under `~/.local/share/dot/`, git stash, branch).
- How it reaches the maintainer: plain file, patch, GitHub issue, or PR.
- Does dot report the record path at the end of the pull, or only on demand?
