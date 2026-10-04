# dot: make shell quoting actually hold end to end

<!-- requirements; migrated from PRD 00078 flat file -->

## Problem

PRD 00045 added `shlex.quote` to `dot rm`, but review found the quoting does not
survive the trip to the shell, and that two other surfaces were never quoted at
all. Three confirmed holes, all in the same theme:

1. **`ShellAdapter` un-quotes what callers quoted.** `ShellAdapter.exe` runs
   `os.path.expandvars` over the *whole* command string after the caller has
   quoted it (`src/lib/buvis/pybase/adapters/shell/shell.py:53-54`, `:125-134`).
   `os.path.expandvars` is a plain string substitution and is quote-unaware, so
   it expands `$VAR` inside the single quotes `shlex.quote` just added.
   Reproduced during the 00045 review: `file_path = "my$EVIL file"` with
   `EVIL="x'; echo PWNED; :'"` produces
   `git ... rm --cached 'myx'; echo PWNED; :' file'`, which executes the injected
   command. The benign case is just as wrong: `dot rm '$HOME'` becomes
   `git rm --cached '/Users/bob'`, acting on the wrong file. This defeats
   `shlex.quote` at **every** call site that uses it — `rm.py`, `unstage.py:30`,
   `commit.py:38`, `tui/commands/secrets.py:59,69,81`, and six call sites in
   `tui/git_ops.py`.

2. **`dot delete` was never quoted.** `CommandDelete._delete_normal` /
   `_delete_encrypted` (`src/tools/dot/commands/delete/delete.py:36-71`) still
   f-string-interpolate `self.file_path` into `cfg rm {path}` and
   `cfg secret remove -c {path}`. It is the same hole 00045 closed in `rm.py`,
   attached to the command that *destroys* files: `dot delete 'x; rm -rf ~'`
   executes.

3. **Quoting does not stop git option/pathspec confusion.** `shlex.quote("-c")`
   returns `-c` unquoted, so a file named `-c` turns
   `cfg secret remove -c <name>` back into the destructive ciphertext-deleting
   mode 00045 removed, and `cfg rm --cached -f` mis-parses. Likewise a filename
   containing `*`, `?` or `[` is glob-expanded by git after the shell hands it
   over, so `dot rm '*'` untracks every matching file. No `--` separator and no
   `:(literal)` pathspec prefix anywhere.

Why `expandvars` exists at all: every dot command registers the `cfg` alias as
`git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}`, and the
whole-command `expandvars` is what resolves it. So it cannot simply be deleted —
the expansion has to be narrowed to the alias text it was added for.

## Solution

Expand environment variables only in the alias body (where `${DOTFILES_ROOT}`
lives), never over caller-supplied command text; quote `delete.py` the way
00045 quoted `rm.py`; and add the `--` end-of-options separator so a
leading-dash filename cannot become a flag.

## Requirements

### Must have

- `ShellAdapter.exe` no longer applies `os.path.expandvars` to the full command
  string. `${DOTFILES_ROOT}` in a registered alias still resolves, so all 11
  `cfg`-alias callers keep working unchanged.
- A filename containing `$VAR` or `${VAR}` reaches the underlying command
  literally, through every `shlex.quote`-guarded call site.
- `CommandDelete._delete_normal` and `_delete_encrypted` pass `self.file_path`
  through `shlex.quote`.
- Both `rm` and `delete` place `--` before the filename so a file named `-c`,
  `-f` or `--force` is treated as a pathspec, not an option.
- Regression tests: (a) a `$VAR` filename is passed literally end to end,
  exercising the real `ShellAdapter` rather than a `MagicMock` — the 00045 tests
  could not catch this because they mocked the adapter and re-derived the
  expected string with `shlex.quote` itself; (b) `dot delete` with a `;`/space
  filename acts on that exact file; (c) a `-c` filename is not parsed as a flag.

### Nice to have

- Audit the remaining `ShellAdapter` callers outside `dot` for command strings
  that relied on the whole-command expansion.

## Success Criteria

- A dotfile named with `$`, `;`, a space, or a leading dash is handled literally
  by both `dot rm` and `dot delete`.
- Every existing dot command still resolves its `cfg` alias; full suite green.
