# bim: split the cli.py god registry

<!-- requirements; migrated from PRD 00055 flat file -->

## Problem

`src/tools/bim/cli.py` is a 773-line monolith: 56 project imports, 13 commands, and 52 hand-rolled `console.success/failure/warning/panic` calls where `console.report_result` (which exists exactly for this) is used 0 times. It is the single busiest source file in the repo (55 commits: feat 23, refactor 21, fix 8), with a 613-line test twin (`tests/tools/bim/test_cli.py`, 29 commits). Every new bim command grows this one file toward the 800-line cap and re-hand-rolls result rendering. The registration pattern for a split already exists (the doc rules subcommands register their own group).

## Solution

Split the CLI into per-group Click modules: each `commands/<group>/` (or a `bim/cli/<group>.py`) exports its own Click group, and the root `cli.py` only composes them. Replace the hand-rolled result rendering with `console.report_result`. Split the test file to mirror the new module boundaries.

## Requirements

### Must have
- Root `bim/cli.py` shrinks to composition (import + register groups); each command group lives in its own module and registers itself (mirroring the existing doc-rules registration).
- Hand-rolled `console.success/failure/...` result blocks are replaced by `console.report_result` where the outcome is a `CommandResult` (behavior/output preserved).
- `test_cli.py` is split to mirror the new modules; all existing assertions preserved.
- No command's user-facing behavior or output changes (characterize first if unsure).

### Nice to have
- A short note in AGENTS.md / bim docs that new commands register their own group (don't grow `cli.py`).

## Success Criteria

- `bim/cli.py` is a thin composition root; no group exceeds the file-size guidance.
- CLI behavior/output identical; bim tests green.
