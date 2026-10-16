---
catchup: force
design: run
default_model: opus
model_tier_rationale: destructive blast radius - resets user edits in $HOME after a save; invented selection predicate (incoming x dirty, mixed-state guard)
---

# dot pull: save local divergence, then let upstream win

Source: `docs/dev/project-management/intake/processed/00089-dot-pull-divergence-report/discovery.md`
(M1-M9, reviewed 2026-10-12). Lands after 00088 and 00090: it reuses 00090's
`fetch()`, `has_upstream()`, `CommandPull` rescue flow and two-host test setup.

## Overview

### Problem Statement
`dot pull` runs a plain `cfg pull`. When an uncommitted edit touches a file the
incoming commits also change, git aborts with "would be overwritten" and the
user must throw the edit away by hand, losing any fix worth sending upstream.
After this PRD, pull saves such edits to a `git apply`-able patch, resets
those files, and lets upstream win.

### Target Users
The solo dotfiles owner who edits dotfiles in place on several hosts.

### Success Metrics
- `tests/tools/dot/test_pull_divergence.py`, `test_pull_divergence_two_hosts.py`,
  `test_divergence.py`, `test_status.py`, `test_pull.py`, `test_tui_app.py` pass.
- Two-host test: B edits `x` uncommitted, A changes `x` and pushes; B pulls ->
  `x` holds A's bytes; the patch carries B's pre-pull `HEAD` full ID and
  `git apply` of it onto that commit rebuilds B's edit byte for byte, including
  CRLF text with `core.autocrlf=false`.
- No conflicting edit -> no patch file, pull output unchanged.

## Functional Decomposition

### Capability: Divergence save

#### Feature: Select divergent paths
- **Description**: Find uncommitted edits the incoming commits would clash with.
- **Inputs**: fetched repo with an upstream; `exclude` paths (rescued host-link targets).
- **Outputs**: sorted list of paths, or a failure.
- **Behavior**: `has_upstream()` false -> no selection, plain pull (today's
  behavior). Otherwise three NUL-split lists (`-z`, drop empty items):
  incoming = `cfg diff --name-only --no-renames -z HEAD...@{u}` (upstream
  changes since the merge base, so local commits never count, M2);
  staged = `cfg diff --cached --name-only --no-renames --ignore-submodules=all -z`;
  unstaged = `cfg diff --name-only --no-renames --ignore-submodules=all -z`.
  Selected = `(staged | unstaged) & incoming`, minus any path `p` where
  `p == e or p.startswith(e + "/")` for an `e` in `exclude` (M9).
  Mixed = `selected & staged & unstaged` (covers worktree restored to `HEAD`
  while the index differs, M8). Mixed non-empty -> failure, nothing reset.
  Any of the three commands erroring -> failure, nothing reset.

#### Feature: Save patch
- **Description**: Write one patch per pull that selects anything (M3, M4).
- **Inputs**: selected paths, dotfiles root.
- **Outputs**: patch file at `<dotfiles_root>/.local/share/dot/divergence/<UTC %Y%m%dT%H%M%SZ>.patch`
  (`dotfiles_root` is `$HOME` in normal use, so this is `~/.local/share/dot/divergence/`).
- **Behavior**: capture the body as raw stdout bytes from
  `git --git-dir=<root>/.buvis --work-tree=<root> --literal-pathspecs diff --binary --full-index --no-renames HEAD -- <selected paths>`,
  using an argv list and `subprocess.run(cwd=self.wd, capture_output=True, text=False)`.
  The working directory is the dotfiles root, matching the existing cfg calls.
  Each selected path is a separate argument; no shell quoting or text decoding
  of the body. This is HEAD vs worktree; with mixed states excluded it equals
  the staged or unstaged change. Do not use `ShellAdapter.exe` for this capture:
  its text mode translates CRLF. Other shell calls keep their existing contract.
  Header lines before the body (git apply skips text before the first
  `diff --git`): `# dot divergence patch`, `# base: <cfg rev-parse HEAD>`,
  `# upstream: <cfg rev-parse @{u}>`, `# host: <socket.gethostname()>`, blank line.
  Encode the header as UTF-8 and append the unchanged body bytes.
  `mkdir(parents=True, exist_ok=True)`, then `atomic_write_bytes`. Target file
  already exists, any `OSError`, a failing git command, or failure reading
  metadata -> failure, nothing reset.

#### Feature: Reset and pull
- **Description**: Reset saved paths, then run the existing pull sequence (M1, M5).
- **Inputs**: selected paths, patch path.
- **Outputs**: `CommandResult` whose `warnings` start with the patch line and
  one line per path reset so far, on success AND on every later failure.
- **Behavior**: one `cfg --literal-pathspecs restore --source=HEAD --staged --worktree -- <path>`
  per selected path, in sorted order (removes paths absent from `HEAD`). The
  save list and reset list are the same `selected` object. A reset error ->
  failure carrying warnings for the resets done before it. Then `cfg pull`,
  submodule steps, secret reveal exactly as today, each failure keeping the
  warnings. Never restore from the patch automatically.

#### Feature: Messages
- Patch saved: `divergence patch saved: <patch path>`
- Per reset: `reset to HEAD, local edit in patch: <path>`
- Mixed: `pull stopped: <p1>, <p2> have both staged and unstaged changes; commit or unstage them first`
- Save failed: `could not save divergence patch: <reason>`
- Detection failed: `divergence check failed: <err>`
- Reset failed: `reset failed for <path>: <err>`
- Pending: `<n> divergence patch(es) pending in <dir>`

### Capability: Surface records

#### Feature: Pending-patch status (M6)
- **Description**: CLI and TUI status warn while any `*.patch` sits in the dir.
- **Inputs**: dotfiles root.
- **Outputs**: `pending_patch_warning(root) -> str | None`.
- **Behavior**: `n = len(list(d.glob("*.patch")))` when `d.is_dir()`, else 0;
  `None` when `n == 0`. `CommandStatus.execute` appends it to `warnings`
  before the "No modifications found" check. TUI `refresh_status` passes
  `pending_patch_warning(self._dotfiles_root) if self._dotfiles_root else None`
  (the root 00088 already hands to `MainScreen`, same guard as link status)
  to `StatusBar.update_info(..., pending=...)`, rendered `bold yellow` after
  the secret count.

#### Feature: Recovery output (M5)
- **Behavior**: CLI already prints `warnings` before the failure line via
  `console.report_result`. TUI `action_pull` renders every pull result as
  `"\n".join([result.output or result.error or "Pull complete", *result.warnings])`.
  `CommandPull.execute` must keep the service result's `warnings` when it
  merges rescue/materialize output (00090).

## Structural Decomposition

### Repository Structure

```
src/tools/dot/
├── divergence.py                # divergence_dir, pending_patch_warning
├── git/service.py               # pull(passphrase, *, exclude, fetched) + helpers
├── commands/pull/pull.py        # pass exclude + fetched=True
├── commands/status/status.py    # pending warning
├── tui/screens/main.py          # action_pull message, refresh_status pending
└── tui/widgets/status_bar.py    # pending segment
tests/tools/dot/
├── test_divergence.py
├── test_pull_divergence.py              # mocked shell
└── test_pull_divergence_two_hosts.py    # real git
```

### Module: dot.divergence
- **Maps to capability**: Surface records, Save patch (location)
- **Responsibility**: Patch dir location and pending count, shared by CLI and TUI.
- **Exports**: `divergence_dir(root) -> Path` (`Path(root) / ".local/share/dot/divergence"`),
  `pending_patch_warning(root) -> str | None`.
- New symbols: `divergence`, `divergence_dir`, `pending_patch_warning`

### Module: dot.git.service
- **Maps to capability**: Divergence save
- **Responsibility**: Select, save, reset, then pull.
- **Exports**: `DotGitService.pull(passphrase=None, *, exclude=(), fetched=False)`
  - `fetched=False` -> runs `self.fetch()` first (error -> `Fetch failed: <err>`);
    `CommandPull` passes `fetched=True` after its own plan fetch, keeping one fetch.
- Prerequisite 00090 creates `fetch` and `has_upstream`; this PRD adds `exclude` and `fetched`.
- New symbols: `exclude`, `fetched`, `fetch`, `has_upstream`

### Module: dot commands and TUI
- **Maps to capability**: Surface records, Recovery output
- **Exports**: unchanged signatures; `StatusBar.update_info(info, error=None, link_problems=0, pending=None)`.
- Prerequisite 00090 creates `plan_rescue`, `CommandLocalize` and `RescuePlan`; this PRD adds `pending`.
- New symbols: `pending`, `plan_rescue`, `CommandLocalize`, `RescuePlan`, `has_upstream`

## Dependency Graph

### Foundation Layer (Phase 0)
- **dot.divergence**: no dependencies.

### Core Layer (Phase 1)
- **dot.git.service pull**: depends on [dot.divergence, 00090 `fetch`/`has_upstream`, pybase `atomic_write_bytes`]

### Integration Layer (Phase 2)
- **commands.pull, commands.status, tui**: depend on [dot.git.service pull, dot.divergence, 00090 `CommandPull` rescue flow]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Shared location and pending logic.

**Tasks**:
- [ ] `src/tools/dot/divergence.py` (no deps) - Acceptance:
  `uv run pytest tests/tools/dot/test_divergence.py` passes: missing dir -> `None`;
  one `.patch` -> `1 divergence patch(es) pending in <dir>`; a non-`.patch`
  file is not counted; after deleting the patch -> `None`.

**Exit Criteria**: `test_divergence.py` green.

### Phase 1: Core
**Goal**: Divergence save inside `DotGitService.pull`.

**Tasks**:
- [ ] Select/save/reset in `DotGitService.pull` (depends on: Phase 0).
  Premise: 00090 is merged; re-check with
  `rg -n "def fetch|def has_upstream" src/tools/dot/git/service.py` (expect 2
  hits). If absent, stop and report; do not implement them here.
  Acceptance: `uv run pytest tests/tools/dot/test_pull_divergence.py` passes
  (mocked shell and binary subprocess, exact command strings/argv asserted): no upstream -> no diff
  commands, plain pull; nothing selected -> no patch, no restore, output
  unchanged; selected -> patch written before first `restore` (call order),
  binary capture runs at the dotfiles root, and raw diff stdout reaches
  `atomic_write_bytes` unchanged after the header;
  save list equals reset list; excluded path and path under an excluded dir
  skipped; mixed path -> failure naming it, zero `restore` calls; read-only
  divergence dir -> failure, zero `restore` calls; existing patch name ->
  failure, zero `restore`; second restore fails -> warnings hold patch line +
  first path only; `cfg pull`, submodule and secret-reveal failures each keep
  patch + all reset warnings (parametrized); existing `test_git_service.py`
  pull tests still pass.

**Exit Criteria**: `test_pull_divergence.py` and `test_git_service.py` green.

### Phase 2: Integration
**Goal**: Wire into `CommandPull`, status, TUI; prove with real git.

**Tasks**:
- [ ] `CommandPull` passes `exclude=[l.target for l in (*plan.moves, *plan.duplicates, *plan.collisions)]`
  and `fetched=True` to `DotGitService.pull`, and keeps the service result's
  `warnings` (depends on: Phase 1). Only the call-argument assertions of
  `pull.assert_called_once_with(` in `tests/tools/dot/test_pull.py` change;
  no assertion is removed. Acceptance: `uv run pytest tests/tools/dot/test_pull.py`
  passes, including a new test that a service failure with warnings comes out
  of `CommandPull.execute` with those warnings.
- [ ] Status: `CommandStatus.execute` appends `pending_patch_warning(self.dotfiles_root)`;
  `StatusBar` `pending` segment; `MainScreen.refresh_status` passes
  `pending_patch_warning(self._dotfiles_root) if self._dotfiles_root else None`
  (existing TUI mock helpers need no edit); `action_pull` message per
  Recovery output (depends on: Phase 1). Acceptance: `uv run pytest tests/tools/dot/test_status.py tests/tools/dot/test_tui_app.py tests/tools/dot/test_status_bar.py`
  passes, with new tests: status with one patch -> one warning naming count 1
  and the dir, none after deletion; status bar shows the pending text; TUI
  pull failure with warnings -> diff pane shows error and patch path (mock
  `status()` to return no entries: with a non-empty file list the selection
  re-render overwrites the pane, a pre-existing bug deferred in batch
  202610121200); CLI `dot pull` (CliRunner, `CommandPull.execute` patched to
  a failure with a patch warning) prints the patch path and the error.
- [ ] Real-git test `tests/tools/dot/test_pull_divergence_two_hosts.py`
  (depends on: previous tasks): reuse 00090's host setup from
  `test_pull_two_hosts.py` (import or move its helpers to `conftest.py`; do
  not change its assertions); real `ShellAdapter`, `CommandPull(...).execute()`.
  Cases: (1) B dirty `x`, A changes `x` -> success, `x` == A's bytes, patch
  has `# base: <B pre-pull HEAD full ID>`, and `git apply` of it in a fresh
  clone checked out at that ID yields B's `x` bytes; binary `x` variant too.
  Repeat with CRLF text (no NUL bytes), `core.autocrlf=false` on every test
  repository, and byte reads/writes: applying the saved patch at the base ID
  restores B's exact CRLF bytes, not LF-normalized content.
  (2) B also dirty `y` untouched upstream -> `y` unchanged, not in patch.
  (3) B unpushed commit on `y` + further dirty `y`, upstream changes only
  `x` -> `y` neither reset nor in patch, whatever the pull outcome.
  (4) `x` staged B, worktree C -> failure naming `x`, index and worktree of
  `x` unchanged, other selected path not reset, no patch; repeat with C ==
  `HEAD` content. (5) A localizes tracked `t` (00090 `CommandLocalize`), B
  has dirty `t` -> B's bytes at the source, `t` a link to it, no patch names
  `t`. (6) divergence dir read-only -> failure, B's `x` edit intact.
  Acceptance: `uv run pytest tests/tools/dot/test_pull_divergence_two_hosts.py` passes.
- [ ] Docs and changelog (depends on: previous tasks): `docs/source/tools/dot.rst`
  and `README.md` describe the divergence patch (location, `git apply` onto
  the base ID, delete when handled, status warning); `CHANGELOG.md`
  `[Unreleased]` gets a `**dot**:` Changed entry for pull saving and resetting
  conflicting edits. Acceptance: `rg -n "divergence" docs/source/tools/dot.rst README.md CHANGELOG.md`
  hits all three.

**Exit Criteria**: `uv run pytest -m dot` and `uv run mypy src/tools/dot src/lib` pass.

## Test Strategy

### Critical Scenarios
- **Happy path**: dirty `x` changed upstream -> patch saved, `x` upstream, patch rebuilds edit.
- **Edge case**: CRLF text with `core.autocrlf=false` -> saved patch applies at its base ID and restores the exact pre-pull bytes.
- **Edge case**: unpushed local commit on `y` -> `y` never selected (merge-base diff).
- **Edge case**: rescued host-link target -> excluded, rescue bytes kept.
- **Error case**: mixed staged/unstaged -> abort before any reset.
- **Error case**: patch write fails -> abort, edits intact.
- **Error case**: failure after save -> patch path and done resets reported in CLI and TUI.

## Risks

- **Save misses a file the reset hits**: one `selected` list feeds both; tested by call-order and list-equality asserts.
- **Fetch-to-pull window**: `cfg pull` re-fetches; a commit landing in that gap
  that touches another dirty file makes git abort as today, so no bytes are lost. Accepted (same as 00090).
- **Patch bytes altered by text capture**: use binary subprocess stdout and
  `atomic_write_bytes`; the CRLF real-git round trip catches newline translation.
  Any capture or metadata failure aborts before reset.
- **00090 ordering**: rescue moves run in `CommandPull` before `DotGitService.pull`,
  so a rescued target shows as a local deletion; `exclude` stops divergence from
  restoring `HEAD` bytes over it (case 5).
