# dot: `dot add <new file>` must track untracked files instead of saying "No changes."

Status: processed, specced as PRD 00093. Recorded 2026-10-12.

## Problem

`dot add .config/gh-agent/config.yml` for a file the dotfiles repo has never
seen prints `No changes.` and stages nothing. The file is addable: the repo
does not ignore it and `git status --untracked-files=all` shows it as `??`.

Root cause, verified in the 0.14.0 source:

- `DotGitService.stage_interactive` (`src/tools/dot/git/service.py:321-325`)
  decides tracked versus untracked by running `cfg ls-files --error-unmatch
  <path>` and looking for the Python phrase `returned non-zero exit status 1`
  in the returned error.
- `ShellAdapter.exe` (`src/lib/buvis/pybase/adapters/shell/shell.py:72`)
  returns git's own stderr whenever there is any: `error: pathspec '...' did
  not match any file(s) known to git`. The phrase never appears, the untracked
  branch never fires, and the code falls through to `cfg add -p <path>`, which
  answers `No changes.` for a file git does not track.
- `tests/tools/dot/test_git_service.py:1184` and `:1200` mock the adapter with
  the exception phrase, so the suite passes while the real path fails (mock
  drift). The fragile match exists at that one site only (`rg "non-zero exit
  status" src` returns a single hit).

Related trap, already recorded in the user's instructions: the bare repo sets
`status.showUntrackedFiles=no`, so any status-based check must pass
`--untracked-files=all` explicitly or it, too, answers with silence.

## Idea (from the user)

`dot add` must support adding untracked files.

## Requirements

1. **R1 Untracked file is tracked**: `dot add <path>` on a file git does not
   know stages it with a plain `cfg add`, from any working directory, with the
   same path resolution against the dotfiles root as today.
2. **R2 Detection independent of exception text**: any error from `ls-files
   --error-unmatch` means untracked, or the check uses
   `git status --porcelain --untracked-files=all -- <path>` and looks for
   `??`. No matching on `CalledProcessError` wording.
3. **R3 Directories unchanged**: the directory path keeps the intent-to-add
   plus `add -p` flow.
4. **R4 Regression test binds to real adapter output**: the test feeds the
   adapter's actual failure string (git's stderr), fails on the current code,
   and passes after the fix. One test runs `ShellAdapter.exe` against a
   throwaway bare repo in `tmp_path` end to end, so this mock drift cannot
   recur silently.
5. **R5 Loud outcome**: after staging, `dot add` reports what it staged; an
   empty result on a path the user named is never silent.

## Open questions

- Should the untracked case offer the same hunk review as directories
  (intent-to-add, then `add -p`), or is a plain add the expected behaviour for
  a brand-new file?
- `src/tools/dot/git/service.py` is under active change on the main checkout
  (hooks path work for 00088); sequence this fix after that lands.
