# dot: make shell quoting actually hold end to end

<!-- tasks; migrated from PRD 00078 flat file -->

## Tasks

### Phase 0: Core
- [ ] Narrow env-var expansion to the alias body in `ShellAdapter` — Acceptance:
      `cfg`-alias commands still resolve `${DOTFILES_ROOT}`, and a `$VAR`
      filename survives quoting literally.
- [ ] Update `tests/lib/pybase/adapters/test_shell_adapter.py:250`, which
      currently pins the vulnerable whole-command expansion — Acceptance: the
      test asserts the new contract and states why the old one was wrong.
- [ ] `shlex.quote` both `delete.py` call sites — Acceptance: a `;`/space
      filename acts on that exact file.
- [ ] Add `--` before the filename in `rm` and `delete` — Acceptance: a file
      named `-c` is untracked, not parsed as the destructive `-c` flag.
