---
design: skip
default_model: sonnet
model_tier_rationale: One flag on two command strings with exact text; every check fails loudly.
---
# `dot unstage` reads its argument as a git pattern and unstages other files

Source: agoge run 2026-11-23, finding 10 of 21 (LOW, verified, lane trudy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

`DotGitService.unstage` passes its path to git as a pathspec. Git reads pathspec magic and globs in it, so `:!a.txt`, `:(top)` or `*` act on files the user did not name. The success line then names the pattern, not the files that were unstaged.

Only a user who types such a pattern is affected, and unstaging loses no data. The sibling code already treats paths literally, so this is an inconsistency: the restore step in `_save_and_reset_divergence` runs `cfg --literal-pathspecs restore ...`, `_diff_argv` in `src/tools/dot/divergence.py` passes `--literal-pathspecs`, and `_staged_report` wraps its path with the `_literal` helper.

The TUI unstage key and the rollback in `dot localize` call the same method with a real path. A file whose name holds a glob character (`a[1].txt`) can make them unstage a neighbour too.

## Solution

`DotGitService.unstage(path)` in `src/tools/dot/git/service.py` treats a given path literally. Both git calls that carry the path get the global git option `--literal-pathspecs`, placed between `cfg` and the git verb. This is the spelling the restore step in the same file already uses.

Exact command strings, with `<quoted>` as `shlex.quote(path)`:

- the pre-check, run only when the path is not on disk: `cfg --literal-pathspecs status --porcelain -- <quoted>`
- the reset: `cfg --literal-pathspecs reset HEAD -- <quoted>`

The call without a path stays `cfg reset HEAD`. Messages and exit codes do not change.

Do not also wrap the path with the `_literal` helper. Under `--literal-pathspecs` git takes a `:(literal)` prefix as part of the file name.

Resulting behaviour, with `a.txt` and `b.txt` staged:

- `dot unstage ':!a.txt'` prints ` ✘ Path :!a.txt is not staged or tracked`, exits 1, and both files stay staged.
- `dot unstage '*'` prints ` ✘ Path * is not staged or tracked`, exits 1, and both files stay staged.
- `dot unstage a.txt` prints ` ✔ a.txt unstaged`, exits 0, and only `b.txt` stays staged.
- With `a[1].txt` and `a1.txt` staged, `dot unstage 'a[1].txt'` unstages only `a[1].txt`.

Glob patterns stop working in `dot unstage`: `dot unstage '*.txt'` no longer unstages the matching files. A pattern the shell expands before `dot` runs was never supported, because the command takes one argument. `docs/source/tools/dot.rst` describes `dot unstage`, so it gains one line that says the argument is a literal path.

## Requirements

### Must have
- With two files staged in a real repository, `CommandUnstage` with `file_path=":!a.txt"` returns `success is False`, `error == "Path :!a.txt is not staged or tracked"`, and both files are still staged.
- The same holds for `file_path="*"`, with `error == "Path * is not staged or tracked"`.
- With `a[1].txt` and `a1.txt` staged in a real repository, `CommandUnstage` with `file_path="a[1].txt"` succeeds and `a1.txt` is the only file still staged.
- `DotGitService.unstage("my file.txt")` issues `cfg --literal-pathspecs reset HEAD -- 'my file.txt'`.
- For a path that is not on disk, the pre-check is `cfg --literal-pathspecs status --porcelain -- <quoted>`.
- `DotGitService.unstage()` still issues `cfg reset HEAD`.
- `docs/source/tools/dot.rst`, section `dot unstage`, says that the argument is a literal path and that git patterns are not expanded.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **dot**: \`dot unstage <path>\` treats its argument as a literal path. A git pattern such as \`:!a.txt\` or \`*\` no longer unstages other files; glob patterns in \`dot unstage\` stop working.`

### Nice to have
- None.

## Implementation

### Module: literal unstage path
- **Location**: `src/tools/dot/git/service.py`, `tests/tools/dot/test_git_service.py`, `tests/tools/dot/test_add_integration.py`, `docs/source/tools/dot.rst`, `CHANGELOG.md`
- **Responsibility**: make `unstage` act only on the path the caller named
- **Exports**: none
- New symbols: `TestCommandUnstageIntegration`, `test_unstage_pattern_argument_unstages_nothing`, `test_unstage_bracketed_name_leaves_the_tracked_neighbour_staged`
- **Risk**: `dot unstage '*.txt'` stops working, if anyone uses it. Four tests in `tests/tools/dot/test_git_service.py`, class `TestDotGitServiceUnstage`, pin the old command strings and must change to the new ones: `test_single_path_is_reset_and_reported`, `test_path_unknown_to_git_and_absent_from_disk_is_refused`, `test_file_on_disk_is_reset_without_asking_git_first` and `test_path_with_embedded_quote_is_shell_escaped`. Change only the expected command text in them. `test_without_path_everything_is_reset` and `test_failure_reports_reset_error` stay green unchanged. The tests in `tests/tools/dot/test_unstage.py` mock the service and are not affected. A directory argument keeps working: a literal pathspec still matches the files under a directory.

### Dependencies
- literal unstage path: No dependencies (foundation)

## Test Strategy

The regression tests use real git, because a mock shell cannot show which files git matches.

They go in `tests/tools/dot/test_add_integration.py`, in a new class `TestCommandUnstageIntegration`. That file already holds the `bare_root` fixture (a real bare repository under `tmp_path`) and the `_git` helper. Each test runs `CommandUnstage(shell=ShellAdapter(suppress_logging=True), dotfiles_root=str(bare_root), file_path=...).execute()` and reads the index with `_git(bare_root, "diff", "--cached", "--name-only")`.

- `test_unstage_pattern_argument_unstages_nothing`, parametrized over `":!a.txt"` and `"*"`: write and stage `a.txt` and `b.txt`; the result fails with `f"Path {pattern} is not staged or tracked"`; the staged names are still `a.txt` and `b.txt`. On the unmodified code `:!a.txt` unstages `b.txt` and `*` unstages both.
- `test_unstage_bracketed_name_leaves_the_tracked_neighbour_staged`: write and stage `a[1].txt` and `a1.txt`; unstage `a[1].txt`; the result succeeds and the staged names are exactly `a1.txt`. On the unmodified code both are unstaged.

The four pinned unit tests in `TestDotGitServiceUnstage` get the new expected command strings.

Evidence from the report, verbatim:

```
**Evidence** (confirmed). With `a.txt` and `b.txt` staged: `dot unstage ':!a.txt'` ->
` ✔ :!a.txt unstaged`, and `b.txt` is the one unstaged. `dot unstage '*'` -> nothing staged.
Shell and option injection held (`$(...)`, `; id`, `-- -h`: all refused). Stays inside the repo.
```

## Tasks

### Phase 0: Fix
- [ ] Add the class `TestCommandUnstageIntegration` with `test_unstage_pattern_argument_unstages_nothing` and `test_unstage_bracketed_name_leaves_the_tracked_neighbour_staged` to `tests/tools/dot/test_add_integration.py`; watch them fail - Acceptance: `uv run pytest tests/tools/dot/test_add_integration.py -k "unstage_pattern_argument or unstage_bracketed_name"` fails on the unmodified code.
- [ ] Add `--literal-pathspecs` to the pre-check and to the reset in `DotGitService.unstage`, and update the expected command strings in the four pinned tests of `TestDotGitServiceUnstage` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/dot/test_add_integration.py tests/tools/dot/test_git_service.py -k "unstage or Unstage"` passes.
- [ ] Add one line to the `dot unstage` section of `docs/source/tools/dot.rst`: the argument is a literal path, git patterns are not expanded (depends on: previous task) - Acceptance: `rg -n "literal path" docs/source/tools/dot.rst` prints one line.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "treats its argument as a literal path" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest -m dot` passes; the project's full test gate (`uv run pytest`) passes.
