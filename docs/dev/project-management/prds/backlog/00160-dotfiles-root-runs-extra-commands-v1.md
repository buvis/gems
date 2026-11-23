---
design: skip
default_model: sonnet
model_tier_rationale: Two quoted values and one guard with exact command text; every check fails loudly.
---
# A `DOTFILES_ROOT` with shell characters runs extra commands

Source: agoge run 2026-11-23, finding 4 of 21 (MEDIUM, verified, lane trudy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

`dot` pastes the dotfiles root unquoted into the git command line that every `dot` command runs. `DotGitService.__init__` builds the string once and registers it as the `cfg` alias. The shell then splits it.

A root with a `;` in it runs the text after the `;` as a command. This happens three times, in the three setup calls of the constructor, before any command checks that the root holds a repository. A root with a space breaks every git call the same way.

The attacker must already control an environment variable, so the security gain is small. The real cost is that `dot` does not work for any root path with a space, and that `dot` writes git config calls into a directory that is not a repository.

## Solution

Two changes in `src/tools/dot/git/service.py`, both in `DotGitService.__init__`.

**1. Quote both uses of the root.** The alias body becomes:

```
git --git-dir=<Q1> --work-tree=<Q2>
```

where `<Q1>` is `shlex.quote(f"{dotfiles_root}/.buvis/")` and `<Q2>` is `shlex.quote(dotfiles_root)`.

- Root `/home/user/dotfiles` gives `git --git-dir=/home/user/dotfiles/.buvis/ --work-tree=/home/user/dotfiles`. This is the same text as today, because the quote function leaves a plain path as it is.
- Root `/home/u s/dots` gives `git --git-dir='/home/u s/dots/.buvis/' --work-tree='/home/u s/dots'`.

The same string is stored in `self._git`. Its two other readers get the quoted form with no further change: the fallback lookup in `_has_unpushed_commits` and the `add -f` hint in `stage_interactive`.

**2. Run the setup calls only in a repository.** After the alias is registered, the constructor calls `self.is_repository()`. When it returns `False`, the constructor returns. It does not call `_ensure_fetch_refspec`, `_ensure_hooks_path` or `_ensure_filter_driver`, so it runs no shell command at all. When it returns `True`, the three calls run in the order they run today.

`is_repository()` itself does not change: it is true when `<root>/.buvis` is a directory.

Resulting behaviour:

- `DOTFILES_ROOT="<S>/dr2;touch pwned_root" dot status` still prints the "is not a dotfiles repository (no .buvis directory)" error and exits 1. The directory holds no new file afterwards.
- With a real bare repository at `<S>/my dots/.buvis`, `dot status` works, and `core.hooksPath` is set to `<S>/my dots/.config/buvis/hooks`.
- `dot setup` is unchanged: it clones into `<root>/.buvis` first and builds the service after that, so the setup calls still run.

Moving `DotGitService` to argument lists is a different option and is out of scope.

## Requirements

### Must have
- Building a `DotGitService` with a real shell at a root named `dr2;touch pwned_root` that holds a real bare `.buvis` creates no file in that root: the root lists only `.buvis`.
- Building a `DotGitService` with a real shell at a root named `my dots` that holds a real bare `.buvis` sets `core.hooksPath` in that repository to `<root>/.config/buvis/hooks`.
- Building a `DotGitService` at a root with no `.buvis` directory registers the `cfg` alias and calls `shell.exe` zero times.
- For root `/home/u s/dots` the alias body is exactly `git --git-dir='/home/u s/dots/.buvis/' --work-tree='/home/u s/dots'`.
- For root `/home/user/dotfiles` the alias body is unchanged.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **dot**: a dotfiles root with a space or a shell character in its path now works. Before, every git call broke on the space, and text after a \`;\` in \`DOTFILES_ROOT\` ran as a command. \`dot\` also runs no git setup call in a root that holds no repository.`

### Nice to have
- None.

## Implementation

### Module: quoted dotfiles root
- **Location**: `src/tools/dot/git/service.py`, `tests/tools/dot/test_git_service_root_quoting.py`, `tests/tools/dot/test_git_service.py`, `tests/tools/dot/test_git_service_filter.py`, `tests/tools/dot/test_setup.py`, `CHANGELOG.md`
- **Responsibility**: keep the dotfiles root one shell word, and touch git config only in a repository
- **Exports**: none
- New symbols: `test_root_with_shell_metacharacters_runs_no_extra_command`, `test_root_with_a_space_reaches_the_repository`, `test_root_without_a_repository_runs_no_setup_command`, `test_alias_quotes_a_root_with_a_space`
- **Risk**: The repository guard breaks mock-shell tests that build the service at a root with no `.buvis` and then assert on the setup calls. These pin the current behaviour and must change so that their root counts as a repository: in `tests/tools/dot/test_git_service.py` the classes `TestDotGitServiceConstruction` (the four fetch-refspec tests) and `TestDotGitServiceHooksPathSelfHeal` (all tests; `test_quotes_dotfiles_root_in_hooks_path` uses its own root `/home/u s/dots`); in `tests/tools/dot/test_git_service_filter.py` the classes `TestFilterDriverSelfHeal` and `TestFilterDriverSelfHealRollback`; in `tests/tools/dot/test_setup.py` the test `test_self_heal_runs_after_clone_and_before_checkout`, where the scripted shell never creates `.buvis`. The fix for the fake roots is the pattern the fixture `gitsecret_is_set_up` already uses: patch `Path.is_dir` to answer true for `<fake root>/.buvis`. The fix for the setup test is a scripted shell that makes the `.buvis` directory when it sees `git clone`. Do not weaken an assertion; change only what makes the root a repository. Other mock-shell tests in `tests/tools/dot` may count constructor calls too; the gate for this PRD is the whole `dot` marker. The existing test `test_ignored_file_is_refused_naming_the_rule_and_the_force_escape` pins the unquoted hint for a plain root and must stay green unchanged. Out of scope, same class of defect: `src/tools/dot/commands/run/run.py` builds its own `cfg` alias from the unquoted environment variable, so `dot run` still splits a root with a space; and `ShellAdapter` expands environment variables in the alias body, so a root path that contains a dollar name is still rewritten inside the quotes. String-built shell commands stay everywhere else in dot.

### Dependencies
- quoted dotfiles root: No dependencies (foundation)

## Test Strategy

The regression tests use real git and the real `ShellAdapter`, because a mock shell cannot show what the shell does with an unquoted `;`.

New file `tests/tools/dot/test_git_service_root_quoting.py`. It is skipped on Windows and when git is missing, like `tests/tools/dot/test_add_integration.py`. Each test sets `GIT_CONFIG_GLOBAL` to the null device and `GIT_CONFIG_NOSYSTEM` to `1`, makes the root under `tmp_path`, and builds the service with `ShellAdapter(suppress_logging=True)`.

- `test_root_with_shell_metacharacters_runs_no_extra_command`: the root is `tmp_path / "dr2;touch pwned_root"` with a real bare repository at `.buvis` (`git init --quiet --bare`). After the service is built, the names in the root are exactly `.buvis`, and `tmp_path / "pwned_root"` does not exist. On the unmodified code the root also holds `pwned_root`, `config` and more.
- `test_root_with_a_space_reaches_the_repository`: the root is `tmp_path / "my dots"` with a real bare `.buvis`. After the service is built, `git --git-dir=<root>/.buvis config core.hooksPath` (run as an argument list, no shell) prints `<root>/.config/buvis/hooks`. On the unmodified code the key is unset.
- `test_root_without_a_repository_runs_no_setup_command`: the root is `tmp_path / "dr2;touch pwned_root"` with no `.buvis`, and the shell is a `MagicMock`. After the service is built, `shell.alias` was called once and `shell.exe` was never called.

One unit test goes in `tests/tools/dot/test_git_service.py`, class `TestDotGitServiceConstruction`: `test_alias_quotes_a_root_with_a_space` asserts the exact alias body for `/home/u s/dots`.

Evidence from the report, verbatim:

```
**Evidence** (confirmed). `DOTFILES_ROOT="<S>/dr2;touch pwned_root" dot status` -> rc 1 with the
"not a dotfiles repository" message, and the directory then holds new files `pwned_root`,
`config`, `core.hooksPath`, `filter.dot-host.clean`, `remote.origin.fetch`: the text after `;`
ran three times, before the repository check. A root with a space breaks every git call the
same way.
```

## Tasks

### Phase 0: Fix
- [ ] Add `test_root_with_shell_metacharacters_runs_no_extra_command`, `test_root_with_a_space_reaches_the_repository` and `test_root_without_a_repository_runs_no_setup_command` in the new file `tests/tools/dot/test_git_service_root_quoting.py`, and `test_alias_quotes_a_root_with_a_space` in `tests/tools/dot/test_git_service.py`; watch them fail - Acceptance: `uv run pytest tests/tools/dot/test_git_service_root_quoting.py tests/tools/dot/test_git_service.py -k "root_with_shell_metacharacters or root_with_a_space or root_without_a_repository or alias_quotes_a_root"` fails on the unmodified code.
- [ ] Quote both uses of the root in `DotGitService.__init__` and return before the three setup calls when `is_repository()` is false (depends on: previous task) - Acceptance: `uv run pytest tests/tools/dot/test_git_service_root_quoting.py tests/tools/dot/test_git_service.py -k "root_with_shell_metacharacters or root_with_a_space or root_without_a_repository or alias_quotes_a_root"` passes.
- [ ] Make the roots of the mock-shell tests named in Risk count as repositories, without weakening an assertion (depends on: previous task) - Acceptance: `uv run pytest -m dot` passes.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "dotfiles root with a space or a shell character" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest -m dot` passes; the project's full test gate (`uv run pytest`) passes.
