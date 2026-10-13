# Discovery: dot add tracks untracked files

## Classification
Depth: standard | Date: 2026-10-13

Source: `idea.md` beside this file.

## Problem
`dot add <file>` on a file the dotfiles repo has never tracked prints `No changes.` and stages nothing (seen with `.config/gh-agent/config.yml`). `stage_interactive` decides "untracked" by looking for the Python `CalledProcessError` phrase, but `ShellAdapter.exe` returns git's own stderr (`error: pathspec ... did not match`). So the untracked branch never fires and the code falls through to `cfg add -p`. Tests mock the adapter with the Python phrase, so the suite passes while the real path fails. Two neighbouring defects in the same path make it worse: cwd-relative paths resolve against the wrong root, and the path goes into shell commands unquoted.

## Requirements

### Must have
- **R1 Untracked file is tracked**: `dot add <path>` on a file git does not know runs a plain `cfg add -- <path>` (no hunk review).
- **R2 Detection independent of exception text**: untracked is decided from git's answer itself (any failure of `ls-files --error-unmatch`, or `status --porcelain --untracked-files=all` showing `??`), never from `CalledProcessError` wording. Any status-based check passes `--untracked-files=all`, because the bare repo sets `status.showUntrackedFiles=no`.
- **R3 Directories unchanged**: a directory keeps the intent-to-add, then `add -p` flow.
- **R4 Ignored files refused loudly**: an untracked file matched by an ignore rule is not added. `dot add` returns failure naming the matching rule (from `check-ignore -v`) and the `git add -f` escape. No force-add, no new flag.
- **R5 Loud outcome**: after staging, `dot add` reports what it staged for the named path. If nothing is staged for a path the user named, it returns a warning or failure, never silent success. `stage_interactive` returns a `CommandResult` instead of `None`.
- **R6 Path resolution from any cwd**: a path that exists relative to cwd is made absolute (or relative to the dotfiles root) before it reaches git, so `dot add config.yml` from `~/.config/gh-agent` stages `~/.config/gh-agent/config.yml`. Paths given relative to the dotfiles root keep working.
- **R7 Quoted paths**: every git command that `stage_interactive` builds uses `shlex.quote(path)` and a `--` guard, matching PRD 00078. Paths with spaces, quotes or a leading dash work.
- **R8 Regression tests bind to real output**: the untracked-detection test feeds git's real stderr, fails on the current code and passes after the fix. One test runs `ShellAdapter.exe` end to end against a throwaway repo in `tmp_path` (untracked, tracked, ignored, directory), so mock drift cannot hide this again.

### Out of scope
- Hunk review or a diff preview for brand-new files (Q1).
- A `--force` option for ignored files (Q3).
- A TUI "add untracked file" action. The TUI never calls `stage_interactive`.
- Changing the fallback where a path that does not exist triggers whole-tree `add -p` (see Open Questions).

## Constraints
- Under CommandResult discipline, `stage_interactive`/`CommandAdd` return results and only `cli.py` renders them.
- No `CalledProcessError` text matching anywhere in dot (the only hit today is `service.py:332`).
- Do not change `ShellAdapter.exe` semantics. Other callers rely on its `(stderr, stdout)` contract.

## Codebase Context
- **Relevant code**: `src/tools/dot/git/service.py:317-336` (`stage_interactive`), `src/tools/dot/commands/add/add.py:25-37` (path resolution, `execute`), `src/tools/dot/cli.py:67-80` (`add`), `src/lib/buvis/pybase/adapters/shell/shell.py:57-75` (`exe` returns stripped stderr on failure).
- **Conventions**: neighbouring service methods already quote, e.g. `ls_files`/`check_ignore` (`service.py:298`, `:312`) and `unstage` (`:348`). Tests are class-based and live in `tests/tools/dot/test_git_service.py` and `test_add.py`.
- **Integration points**: `tests/tools/dot/test_git_service.py:1184` and `:1200` mock the Python phrase (mock drift). `:1176-1178` asserts the unquoted `cfg ls-files --error-unmatch it's.txt`, so it locks in the R7 bug and must be corrected, not kept. `test_add.py:104-142` asserts `stage_interactive` call args and will need the new return value.
- **Similar implementation**: `src/tools/klyreon/run/staging.py:52` runs `ls-files --error-unmatch -- <rel>` with an argv list and reads the exit code, the shape R2 wants (no cross-tool import, pattern only).

## Success Criteria
- From `~/.config/gh-agent`, `dot add config.yml` on an untracked file stages it, and `cfg diff --cached --name-only` lists `.config/gh-agent/config.yml`.
- `dot add <ignored file>` exits non-zero with the ignore rule in the message.
- The new regression test fails on master `c03db9b5` and passes after the fix. The full `pytest -m dot` run is green.

## Risks
- **The R5 check after staging misreads a partial `add -p`** (the user declines every hunk of a tracked file): treat "nothing staged" as a warning, not a failure, for tracked files and directories. Only an untracked file that stays unstaged is a failure.
- **An end-to-end test needs a real git**: CI already has git. Build the repo in `tmp_path` with `git init` and point the `cfg` alias at it through `ShellAdapter.alias`.

## Open Questions
- When the named path does not exist, `CommandAdd` warns and runs whole-tree `add -p` (`add.py:30-33`). With R5 in place, should a missing named path fail instead? Left out of scope by default. create-prd should confirm or pull it in.

## Discovery Log

### Q1: Untracked file - plain add, or intent-to-add + `add -p` like directories?
**Answer**: Plain add (`cfg add -- <path>`), no hunk review.

### Q2: Fix the neighbouring cwd-relative path bug and the unquoted paths in `stage_interactive` in this PRD?
**Answer**: Fix both here.

### Q3: Untracked file matched by a gitignore rule - refuse, force-add, or add a `--force` flag?
**Answer**: Refuse loudly, naming the rule and the `git add -f` escape.

### Inferred (no question asked)
- Sequencing after 00088: settled. `prds/done/00088-dot-host-links-materialize-v1.md` has landed.
- Problem trigger and success criteria: given in `idea.md` (repeatable failure on a real file).
