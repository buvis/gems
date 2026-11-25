---
design: skip
default_model: sonnet
model_tier_rationale: One small check with exact message text; every check fails loudly.
---
# `dot` skips git-secret in silence when `.gitsecret` is a file or a dangling link

Source: agoge run 2026-11-23, finding 9 of 21 (LOW, mocked, lane trudy), `docs/dev/project-management/audit-results/agoge-2026-11-23.md`.

## Problem

`dot` runs the git-secret `hide` step only when `<root>/.gitsecret` is a directory. This was added so that a repository that never set up git-secret works. The same test also skips a damaged setup: a `.gitsecret` that is a regular file, or a symlink whose target is gone.

In that state `dot status` and `dot commit` exit 0 with no warning, and nothing is encrypted. A broken `.gitsecret` (a bad checkout, a bad link) turns encryption off without a word. The case is unlikely. The cost when it happens is a plaintext secret in a commit.

## Solution

`dot` skips the git-secret steps only when `.gitsecret` does not exist at all. When it exists but is not a directory, the command fails.

A new private method on `DotGitService` in `src/tools/dot/git/service.py`, `_check_git_secret_setup() -> str | None`, returns the error text for a damaged setup and `None` otherwise. With `marker = self.wd / ".gitsecret"` it decides in this order:

1. `git-secret` is not installed (`self.shell.is_command_available("git-secret")` is false): `None`.
2. `marker.is_dir()` is true (a directory, or a symlink to one): `None`.
3. `os.path.lexists(marker)` is false: `None`.
4. Otherwise: the error text.

Exact error text, with `{marker}` as the full path `<root>/.gitsecret`:

```
git-secret setup is damaged: {marker} exists but is not a directory; restore it, or remove it if this repository keeps no secrets
```

`uses_git_secret()` keeps its signature and its result: `True` only when git-secret is installed and `.gitsecret` is a directory.

Two callers use the new method:

- `_hide_secrets` calls it first. When it returns text, `_hide_secrets` returns that text and runs no shell command.
- `pull` calls it as its first step, before the fetch. When it returns text, `pull` returns `CommandResult(success=False, error=<text>)` and runs no shell command.

Resulting behaviour with git-secret installed and `.gitsecret` a regular file or a dangling symlink:

- `dot status` prints ` ✘ Error hiding secrets: git-secret setup is damaged: <root>/.gitsecret exists but is not a directory; restore it, or remove it if this repository keeps no secrets` and exits 1. The prefix comes from the existing code in `src/tools/dot/commands/status/status.py`.
- `dot commit <message>` prints ` ✘ ` and the error text, exits 1, and makes no commit.
- `dot pull` prints ` ✘ ` and the error text, exits 1, and fetches nothing.
- The TUI shows the error text in its status bar through the existing `hide_error` path.

Unchanged:

- No `.gitsecret` at all: the git-secret steps are skipped with no message, exit 0.
- `.gitsecret` is a directory: the steps run as today.
- git-secret is not installed: nothing is checked. This matches today's rule that a repository with a good `.gitsecret` directory also passes in silence on a machine without git-secret.
- `has_uncommitted_changes` still ignores a failed hide step.

## Requirements

### Must have
- With git-secret reported as installed and `.gitsecret` a regular file, `DotGitService.status()` returns the exact error text as its second value and runs no `secret hide` command.
- The same holds when `.gitsecret` is a symlink to a missing target.
- In both states `DotGitService.commit("msg")` returns `success is False` with the exact error text and runs no `cfg commit` command.
- In both states `DotGitService.pull()` returns `success is False` with the exact error text and calls `shell.exe` zero times.
- With git-secret reported as not installed and `.gitsecret` a regular file, `DotGitService.status()` returns `None` as its second value.
- With no `.gitsecret`, the three existing tests in `TestRepoWithoutGitSecret` stay green unchanged.
- `docs/source/tools/dot.rst`, section `dot status`, says that the commands fail when `.gitsecret` exists but is not a directory.
- `CHANGELOG.md` gains this line under `[Unreleased]` / `### Fixed`: `- **dot**: \`dot status\`, \`dot commit\` and \`dot pull\` fail when \`.gitsecret\` exists but is not a directory (a regular file, a dangling link). Before, they skipped the git-secret steps without a word and exited 0.`

### Nice to have
- None.

## Implementation

### Module: damaged git-secret setup check
- **Location**: `src/tools/dot/git/service.py`, `tests/tools/dot/test_git_service.py`, `docs/source/tools/dot.rst`, `CHANGELOG.md`
- **Responsibility**: fail loud when `.gitsecret` exists but cannot be a git-secret setup
- **Exports**: none
- New symbols: `_check_git_secret_setup`, `TestDamagedGitSecretSetup`, `test_gitsecret_that_is_not_a_directory_fails_the_hide_step`, `test_gitsecret_that_is_not_a_directory_blocks_the_commit`, `test_gitsecret_that_is_not_a_directory_fails_pull_before_the_fetch`, `test_damaged_gitsecret_is_not_checked_without_git_secret`
- **Risk**: The order of the checks matters for the existing tests. The autouse fixture `gitsecret_is_set_up` in `tests/tools/dot/test_git_service.py` patches only `Path.is_dir` for the fake root `/home/user/dotfiles`. The `is_dir()` check must come before the `lexists` check, or every secret test at the fake root turns into a skip. With the order above no existing test pins the old behaviour and none must change. The rule "not checked when git-secret is not installed" is this PRD's reading of the decision, chosen to match today's silence for a good setup on a machine without the tool; the test `test_damaged_gitsecret_is_not_checked_without_git_secret` pins it. A user whose `.gitsecret` is a stray file in a repository with no secrets now gets an error on `status`, `commit` and `pull` until the file is removed; the message says so. `dot pull` fails before the fetch, so a damaged setup also blocks a pull that would repair it; `dot run pull` remains as the way out. The evidence is mocked, so the real git-secret is not proven to misbehave in this state.

### Dependencies
- damaged git-secret setup check: No dependencies (foundation)

## Test Strategy

The evidence is mocked: the lane used a stub `git-secret` and had no gpg key in its scratch directory. The regression tests are mocked the same way, with a scripted `MagicMock` shell. A real check needs the real `git-secret` and a gpg key; `tests/tools/dot/test_pull_secret_divergence_two_hosts.py` already builds both and is the place where one can run. This PRD does not add one.

The new tests go in `tests/tools/dot/test_git_service.py`, in a new class `TestDamagedGitSecretSetup` beside `TestRepoWithoutGitSecret`. They use the same kind of fixture: a service at `tmp_path` with `shell.is_command_available.return_value = True` and the constructor calls forgotten. Each state is made on disk: `(tmp_path / ".gitsecret").write_text("x")` for the regular file, `(tmp_path / ".gitsecret").symlink_to(tmp_path / "gone")` for the dangling link. The tests that cover both states are parametrized over the two.

- `test_gitsecret_that_is_not_a_directory_fails_the_hide_step`: `status()` returns the exact error text as `hide_error`; no issued command contains `secret hide`.
- `test_gitsecret_that_is_not_a_directory_blocks_the_commit`: `commit("msg")` fails with the exact error text; no issued command starts with `cfg commit`.
- `test_gitsecret_that_is_not_a_directory_fails_pull_before_the_fetch`: `pull()` fails with the exact error text; `shell.exe` was not called.
- `test_damaged_gitsecret_is_not_checked_without_git_secret`: with `shell.is_command_available.return_value = False` and a regular file, `status()` returns `None` as `hide_error`.

Evidence from the report, verbatim:

```
**Evidence** (mocked: a stub `git-secret`, no gpg key in scratch). With `.gitsecret/` a directory
the stub log shows `hide -m`; with `.gitsecret` a regular file, a dangling symlink, or removed, it
shows `list` only, and `dot status` / `dot commit` exit 0 with no warning. With the entry removed
and the secret no longer ignored, `dot add secret.env` then `dot commit` put the marker in
`HEAD:secret.env`.
```

## Tasks

### Phase 0: Fix
- [ ] Add the class `TestDamagedGitSecretSetup` with `test_gitsecret_that_is_not_a_directory_fails_the_hide_step`, `test_gitsecret_that_is_not_a_directory_blocks_the_commit`, `test_gitsecret_that_is_not_a_directory_fails_pull_before_the_fetch` and `test_damaged_gitsecret_is_not_checked_without_git_secret` to `tests/tools/dot/test_git_service.py`; watch the first three fail - Acceptance: `uv run pytest tests/tools/dot/test_git_service.py -k "gitsecret_that_is_not_a_directory"` fails on the unmodified code.
- [ ] Add `_check_git_secret_setup` to `DotGitService` with the exact error text and call it first in `_hide_secrets` and in `pull` (depends on: previous task) - Acceptance: `uv run pytest tests/tools/dot/test_git_service.py` passes.
- [ ] Add one sentence to the `dot status` section of `docs/source/tools/dot.rst`: the three commands fail when `.gitsecret` exists but is not a directory (depends on: previous task) - Acceptance: `rg -n "not a directory" docs/source/tools/dot.rst` prints one line.
- [ ] Add the `### Fixed` line to `CHANGELOG.md` under `[Unreleased]` (depends on: previous task) - Acceptance: `rg -n "exists but is not a directory" CHANGELOG.md` prints one line.

## Success Criteria

- `uv run pytest -m dot` passes; the project's full test gate (`uv run pytest`) passes.
