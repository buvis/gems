---
design: run
default_model: sonnet
model_tier_rationale: exact git commands and messages given; three existing init tests repointed under a pinned premise; real-git test catches a wrong setup
---

# dot host links: hooksPath self-heal and `dot setup`

Source: `docs/dev/project-management/intake/new/00088-dot-materialize-host-config/discovery.md`
(PRD D of 3, M10 + M11). Depends on 00088 (`CommandMaterialize`,
`DotGitService.hooks_path()`, the shipped hooks). Independent of 00090.

## Overview

### Problem Statement
Git's core.hooksPath lives in the bare repo's untracked config, so the pre-commit
gate and the 00088 relink hooks run only on hosts someone wired by hand. dot
also cannot set up a fresh machine. This PRD makes every dot run set
hooksPath when unset, warns when the hooks are missing, and adds `dot setup`.

### Target Users
The solo dotfiles owner bringing up a new host.

### Success Metrics
- `tests/tools/dot/test_git_service.py`, `test_status.py`, `test_setup.py`,
  `test_setup_real_git.py` pass.
- Real-git test: `dot setup <url>` into an empty temp `$HOME` -> hooksPath
  set, upstream set, files checked out, manifest links present; a later
  `cfg checkout` fires `post-checkout` and relinks a removed link.

## Functional Decomposition

### Capability: Self-heal

#### Feature: Set hooksPath when unset
- **Description**: Same pattern as the fetch refspec self-heal
  (`src/tools/dot/git/service.py:36-42`).
- **Inputs**: none (runs in `DotGitService.__init__`, after the refspec step).
- **Behavior**: `cfg config core.hooksPath`; error or blank output ->
  `cfg config core.hooksPath <shlex-quoted dotfiles_root>/.config/buvis/hooks`
  (absolute path, no `~`). A set value is never changed.

#### Feature: Hook health warnings
- **Description**: `DotGitService.check_hooks() -> list[str]`.
- **Behavior**: dir = `hooks_path()`; `None` -> `[]`. Dir missing ->
  `["hooks dir missing: <dir>"]`. Else `<dir>/pre-commit` missing ->
  `["pre-commit hook missing: <dir>/pre-commit"]`. Else `[]`.
  `CommandStatus.execute` appends these to its warnings.

### Capability: Setup

#### Feature: `dot setup [URL]`
- **Description**: Bring up dotfiles on a fresh host.
- **Inputs**: `URL` argument; when absent, `DotSettings.remote_url`
  (`BUVIS_DOT_REMOTE_URL`); both absent -> `console.panic("remote URL required:
  dot setup <url> or set BUVIS_DOT_REMOTE_URL")`.
- **Outputs**: `CommandResult`; info lines `cloned <url>`, `checked out`,
  then the materialize info lines; materialize warnings passed through.
- **Behavior**: `CommandSetup(shell, dotfiles_root, remote_url).execute()`:
  1. `<root>/.buvis` exists -> failure `already set up: <root>/.buvis exists`.
  2. `git clone --bare <quoted url> <quoted root>/.buvis`; error -> failure
     `clone failed: <err>`.
  3. Build `DotGitService` (alias, refspec and hooksPath self-heal run here).
  4. `cfg config status.showUntrackedFiles no` (a `$HOME` work-tree is
     otherwise all untracked).
  5. `cfg fetch origin`; branch = `cfg rev-parse --abbrev-ref HEAD`;
     `cfg branch --set-upstream-to=origin/<branch>`. Errors -> warning
     `upstream not set: <err>` (setup continues; pull rescue then skips).
  6. `cfg checkout`; error -> failure
     `checkout conflicts with existing files, nothing overwritten:\n<err>\n`
     `move them away, then run: dot run checkout` and stop. Never `-f`.
  7. `CommandMaterialize(shell, dotfiles_root, install_hooks=True).execute()`
     and merge its info and warnings.

## Structural Decomposition

### Repository Structure

```
src/tools/dot/
├── git/service.py                 # + _ensure_hooks_path, check_hooks
├── commands/setup/{__init__,setup}.py
├── commands/status/status.py      # + check_hooks warnings
├── settings.py                    # + remote_url
└── cli.py                         # setup command
```

### Module: git.service
- **Maps to capability**: Self-heal
- **Exports**: `DotGitService.check_hooks()`; private `_ensure_hooks_path()`.
- New symbols: `_ensure_hooks_path`, `check_hooks`
- New symbols: `CommandMaterialize`, `hooks_path` (created by prerequisite PRD 00088, must exist before this PRD starts)

### Module: commands.setup
- **Maps to capability**: Setup
- **Exports**: `CommandSetup(shell, dotfiles_root, remote_url)`;
  `DotSettings.remote_url: str | None = None`.
- New symbols: `CommandSetup`, `setup`, `remote_url`, `DotSettings.remote_url`, `BUVIS_DOT_REMOTE_URL`

## Dependency Graph

### Foundation Layer (Phase 0)
- **git.service self-heal**: depends on 00088 `hooks_path()`.

### Core Layer (Phase 1)
- **commands.setup**: depends on [git.service, 00088 CommandMaterialize]

### Integration Layer (Phase 2)
- **cli, commands.status**: depend on [commands.setup, git.service]

## Implementation Phases

### Phase 0: Foundation
**Goal**: hooksPath self-heal and health check.

**Tasks**:
- [ ] `_ensure_hooks_path` + `check_hooks` (no deps) - Premise: in
  `tests/tools/dot/test_git_service.py`,
  `test_does_not_reset_fetch_refspec_when_already_configured`,
  `test_resets_fetch_refspec_when_check_errors` and
  `test_resets_fetch_refspec_when_check_returns_empty` assert
  `shell.exe.call_count == 1/2/2`; re-check with
  `rg -n "assert shell.exe.call_count == [12]$" tests/tools/dot/test_git_service.py`
  before editing, and if those three are not found stop and report. Change
  only those asserts to count calls whose command contains
  `remote.origin.fetch` (same 1/2/2). Acceptance: new tests (unset -> set to
  `<root>/.config/buvis/hooks`; set -> no write; each `check_hooks` branch
  using `tmp_path`) and the three repointed tests pass under
  `uv run pytest tests/tools/dot/test_git_service.py`.

**Exit Criteria**: git service tests green.

### Phase 1: Core
**Goal**: `CommandSetup`, proven against real git.

**Tasks**:
- [ ] `CommandSetup` (depends on: Phase 0) - Acceptance:
  `uv run pytest tests/tools/dot/test_setup.py` passes with a mocked shell:
  existing `.buvis` -> failure and no `exe` call; clone error -> failure;
  checkout error -> failure naming `dot run checkout`, no `-f` in any
  command, materialize not run; upstream error -> warning, setup continues.
- [ ] Real-git test `tests/tools/dot/test_setup_real_git.py` (depends on:
  previous task): temp origin repo holding a manifest entry and the three
  hook files, temp `$HOME` with the source file present, real
  `ShellAdapter`, git identity via `monkeypatch.setenv`, `DOTFILES_ROOT`
  set, `PATH` prefixed with `Path(sys.executable).parent` so the hook finds
  `dot`. Assert hooksPath value, upstream set, link present; delete the link,
  run `cfg checkout -- .` through the service, assert the link is back.
  Second case: a conflicting file in `$HOME` -> failure, file bytes
  unchanged. Acceptance: `uv run pytest tests/tools/dot/test_setup_real_git.py`
  passes.

**Exit Criteria**: setup tests green.

### Phase 2: Integration
**Goal**: CLI, setting and status warnings.

**Tasks**:
- [ ] `remote_url` setting, `dot setup [URL]` CLI, `check_hooks` warnings in
  `CommandStatus` (depends on: Phase 1) - Acceptance: new tests in
  `tests/tools/dot/test_dot_commands.py` (argument wins over setting; setting
  used when no argument; neither -> panic message) and
  `tests/tools/dot/test_status.py` (missing pre-commit -> warning) pass.
- [ ] Docs and changelog: `docs/source/tools/dot.rst` and `README.md` cover
  `dot setup`, `BUVIS_DOT_REMOTE_URL` and the hooksPath self-heal;
  `CHANGELOG.md` `[Unreleased]` gets a `**dot**:` Added entry for `dot setup`
  and the self-heal (depends on: previous task) - Acceptance:
  `rg -n "dot setup" docs/source/tools/dot.rst README.md CHANGELOG.md` hits
  all three.

**Exit Criteria**: `uv run pytest -m dot` and `uv run mypy src/tools/dot` pass.

## Test Strategy

### Critical Scenarios
- **Happy path**: setup into empty `$HOME` -> files, hooksPath, links.
- **Edge case**: hooksPath already set to another dir -> left unchanged.
- **Error case**: `$HOME` file conflicts with checkout -> reported, untouched.
- **Error case**: `.buvis` exists -> refused before any git call.

## Risks

- **Hooks-ordering on first checkout**: hooksPath is set before checkout, but
  the hook files arrive with that checkout, so `post-checkout` may not fire
  on it; step 7 runs materialize anyway.
- **Bare repo `HEAD` branch**: `git clone --bare` sets `HEAD` to the remote
  default branch, so `rev-parse --abbrev-ref HEAD` names it; a remote with no
  default branch fails at step 5 as a warning.
- **Real-git test needs the `dot` entry point** in the venv bin; `uv sync`
  installs it.
