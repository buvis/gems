# Discovery: dot add tracks untracked files

## Classification
Depth: standard | Date: 2026-10-13

Source: `idea.md` beside this file.

## Problem
`dot add <file>` on a file the dotfiles repo has never tracked prints `No changes.` and stages nothing (seen with `.config/gh-agent/config.yml`). `stage_interactive` decides "untracked" by looking for the Python `CalledProcessError` phrase, but `ShellAdapter.exe` returns git's own stderr (`error: pathspec ... did not match`). So the untracked branch never fires and the code falls through to `cfg add -p`. Tests mock the adapter with the Python phrase, so the suite passes while the real path fails. Two neighbouring defects in the same path make it worse: cwd-relative paths resolve against the wrong root, and the path goes into shell commands unquoted.

## Requirements

### Must have
- **R1 Untracked file is tracked**: `dot add <path>` on a file git does not know runs a plain `cfg add -- <path>` (no hunk review).
- **R2 Detection independent of exception text**: distinguish tracked, untracked, ignored, and lookup failure from git's response, never from `CalledProcessError` wording. A lookup failure stops staging and returns failure; it is not evidence that a file is untracked. Ignored files follow R4. Design chooses the detection method; any status-based check passes `--untracked-files=all`, because the bare repo sets `status.showUntrackedFiles=no`.
- **R3 Directories unchanged**: an actual directory, not a symlink to one, keeps the intent-to-add, then `add -p` flow.
- **R4 Ignored files refused loudly**: an untracked file matched by an ignore rule is not added. `dot add` returns failure naming the matching rule (from `check-ignore -v`) and the `git add -f` escape. No force-add, no new flag.
- **R5 Loud outcome**: after staging, `dot add` reports the final staged state for the named path, including pre-existing staged changes, labelled as currently staged rather than attributed to this invocation. An empty final staged state produces a warning for tracked files and directories, or failure for an untracked file that remains unstaged, never silent success. `stage_interactive` returns a `CommandResult` instead of `None`.
- **R6 Path resolution from any cwd**: a path that exists relative to cwd is made absolute (or relative to the dotfiles root) before it reaches git, so `dot add config.yml` from `~/.config/gh-agent` stages `~/.config/gh-agent/config.yml`. Paths given relative to the dotfiles root keep working. Normalization preserves the named symlink instead of substituting its target: a symlink, including one to a directory, is staged as the link itself.
- **R7 Quoted and literal paths**: every git command that `stage_interactive` builds uses `shlex.quote(path)` and a `--` guard, matching PRD 00078. Every lookup, staging operation, and verification treats the named path literally, without Git wildcard matching. Paths with spaces, quotes, a leading dash, or Git pattern characters work. Regression coverage includes untracked `file[1].txt` beside tracked `file1.txt`: detection and staging select only the named file.
- **R8 Regression tests bind to real output**: any mocked Git failures use git's real stderr rather than invented Python exception wording. The untracked-file regression fails on the current code and passes after the fix. Integration coverage runs `CommandAdd.execute` through the real `ShellAdapter` against a throwaway bare `.buvis` repo with a separate work tree in `tmp_path` and `status.showUntrackedFiles=no`. Cover untracked, tracked, ignored, and directory inputs, including a nested-cwd invocation; assert returned results and actual index contents, so mock drift cannot hide this again.

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
- **Similar implementation**: `src/tools/klyreon/run/staging.py:52` runs `ls-files --error-unmatch -- <rel>` with an argv list and reads the exit code (no cross-tool import, pattern only). Its boolean result does not distinguish untracked from lookup failure; that classification must not be copied for R2.

## Success Criteria
- From `~/.config/gh-agent`, `dot add config.yml` on an untracked file stages it, and `cfg diff --cached --name-only` lists `.config/gh-agent/config.yml`.
- `dot add <ignored file>` exits non-zero with the ignore rule in the message.
- A failed tracking lookup returns failure and does not attempt staging.
- Adding untracked `file[1].txt` beside tracked `file1.txt` stages the literal named file and leaves the neighbour's index entry unchanged.
- Declining every new hunk when the named tracked file already has staged changes reports those changes as currently staged, without claiming new staging; an empty final staged state produces a warning.
- Adding an untracked symlink stages the link itself, including a link to a directory, without staging the target's contents.
- The new regression test fails on master `c03db9b5` and passes after the fix. The full `pytest -m dot` run is green.

## Risks
- **The R5 check confuses final state with new staging**: declining every hunk may leave earlier staged changes intact. Report the final staged state without claiming this invocation changed it; warn only when that state is empty for tracked files and directories. An untracked file that stays unstaged is a failure.
- **An integration test needs a real git and the production repository shape**: CI already has git. Create the bare repo with `git init --bare <root>/.buvis`, use `<root>` as its work tree, and set `status.showUntrackedFiles=no`. Exercise `CommandAdd.execute` through the real adapter and service alias setup rather than testing the adapter alone.

## Open Questions
- When the named path does not exist, `CommandAdd` warns and runs whole-tree `add -p` (`add.py:30-33`). With R5 in place, should a missing named path fail instead? Left out of scope by default. create-prd should confirm or pull it in.

## Discovery Log

### Q1: Untracked file - plain add, or intent-to-add + `add -p` like directories?
**Answer**: Plain add (`cfg add -- <path>`), no hunk review.

### Q2: Fix the neighbouring cwd-relative path bug and the unquoted paths in `stage_interactive` in this PRD?
**Answer**: Fix both here.

### Q3: Untracked file matched by a gitignore rule - refuse, force-add, or add a `--force` flag?
**Answer**: Refuse loudly, naming the rule and the `git add -f` escape.

### Review decisions (2026-10-13)
All five findings resolved with option 1:
1. R2: require distinct tracking states and lookup failure; a failed lookup stops staging, with the detection method left to design.
2. R7: preserve literal path identity through detection, staging, and verification; test a bracketed filename beside a matching neighbour.
3. R8: exercise `CommandAdd.execute` through the real adapter in a bare-repo fixture with hidden untracked files and a nested-cwd case.
4. R5: report the final staged state, including existing staged changes, without attributing them to this invocation.
5. R6: preserve named symlinks and stage the link itself; directory flow applies to actual directories.

### Inferred (no question asked)
- Sequencing after 00088: settled. `prds/done/00088-dot-host-links-materialize-v1.md` has landed.
- Problem trigger and success criteria: given in `idea.md` (repeatable failure on a real file).
