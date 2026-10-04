# dot rm: untrack (not destroy) secrets, and quote the filename

<!-- requirements; migrated from PRD 00045 flat file -->

## Problem

`dot rm` has a data-loss trap and a shell-injection hole, both in `src/tools/dot/commands/rm/rm.py`:

1. **Encrypted rm destroys both copies.** For a git-secret file, the "encrypted" path runs `cfg secret remove -c` (`:46`, deletes the `.secret` ciphertext) and then unlinks the plaintext (`:60-65`). So `dot rm ~/.ssh/config` — which a user runs expecting "stop tracking, keep my file" (the normal path is `rm --cached`, file preserved, `:38`) — deletes the only plaintext copy **and** its encrypted copy. It is recoverable only from an old committed `.secret` blob plus the GPG key. This makes `dot rm` == `dot delete` for secrets, which is not what "rm" means here.

2. **Filename injected into a `shell=True` command.** `self.file_path` is f-string-interpolated into `cfg rm --cached {self.file_path}` (`:38`) and `cfg secret remove -c {self.file_path}` (`:46`), executed via `ShellAdapter.exe` (`shell=True`). A dotfile whose name contains `;`, `$()`, a backtick, or a space runs injected shell or mis-parses.

## Solution

Make the encrypted rm path **untrack without deleting the plaintext** (drop the `-c`, keep the file; reserve destruction for `dot delete`), and `shlex.quote` the filename everywhere it enters the shell command. `shell=True` is required for the `cfg` alias, so quote the variable rather than removing the shell.

## Requirements

### Must have
- Encrypted `dot rm <file>` untracks the secret (removes it from git-secret management and un-tracks it) but **leaves the plaintext file on disk** — symmetry with the normal `rm --cached` path.
- `dot delete` remains the command that removes the file from disk (unchanged).
- `self.file_path` is passed through `shlex.quote` in both `cfg rm --cached ...` and the encrypted-path command.
- Regression tests: (a) encrypted rm leaves the plaintext file present and untracked; (b) a filename containing a space / `;` is handled literally (no injection, no mis-parse) — assert the file with the odd name is the one acted on.

### Nice to have
- A one-line note in `docs/source/tools/dot.rst` clarifying `rm` = untrack, `delete` = remove from disk.

## Success Criteria

- `dot rm` never deletes a file from disk; only `dot delete` does.
- Odd filenames are safe; dot tests green.
