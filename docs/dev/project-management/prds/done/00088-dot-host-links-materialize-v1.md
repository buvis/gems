---
design: run
default_model: sonnet
model_tier_rationale: every rule, message and path is fixed below; additive code and tests, no deletes; Windows branch tested by monkeypatch
---

# dot host links: manifest, materialize, hooks, link status

Source: `docs/dev/project-management/intake/processed/00088-dot-materialize-host-config/discovery.md`
(PRD A of 3; B+C = 00090 localize + pull rescue, D = 00091 self-heal + setup).

## Overview

### Problem Statement
Some config sits where a tool expects it but differs per host
(`~/.config/gita/repos.csv`, `~/.config/buvis/buvis-postup.yaml`). Tracked, one
host's values leak to all hosts; untracked, it has no home. dot has no way to
say "this path is per host". This PRD adds a tracked manifest of host-specific
paths and the code that turns each entry into a link to a host-local real file.

### Target Users
The solo dotfiles owner running dot on macOS, Linux and Windows hosts.

### Success Metrics
- `tests/tools/dot/test_hostlinks_manifest.py`, `test_hostlinks_linker.py`,
  `test_hostlinks_hooks.py`, `test_materialize.py`, `test_link_status.py` pass.
- Temp-`$HOME` test: manifest with one file and one dir entry, both sources
  present -> `dot materialize` creates both links; second run prints nothing.
- Target is a real file -> one warning, file bytes unchanged.
- Source missing -> one warning, no link created.

## Functional Decomposition

### Capability: Manifest
One tracked text file, `<dotfiles_root>/.config/buvis/host-links`.

#### Feature: Parse manifest
- **Description**: Turn manifest text into validated entries plus line errors.
- **Inputs**: File text. Line format `<target> => <source>`, both sides
  `$HOME`-relative, POSIX `/` separators. Blank lines and lines whose first
  non-space char is `#` are skipped. Each side is stripped of whitespace.
- **Outputs**: `(list[HostLink], list[str])`. Error text is exactly
  `host-links:<lineno>: <reason>` with reason one of: `missing '=>'`,
  `empty path`, `absolute path`, `'..' not allowed`, `target equals source`,
  `duplicate target <target>`.
- **Behavior**: split on the first `=>`. A side is absolute when
  `PurePosixPath(s).is_absolute()`, `PureWindowsPath(s).is_absolute()`,
  `PureWindowsPath(s).drive` is non-empty, or it starts with `~`. Any `..`
  path part is rejected (stricter than "escapes $HOME", no resolve needed).
  Bad lines are reported and skipped, never guessed. A missing file yields
  `([], [])`.

### Capability: Linking

#### Feature: Reconcile links
- **Description**: For each entry, check or create the link `target -> source`.
- **Inputs**: `root: Path`, `apply: bool`.
- **Outputs**: `(changes: list[str], problems: list[str])`. Manifest errors are
  prepended to problems.
- **Behavior**: `t = root/target`, `s = root/source`, `link = _read_link(t)`
  (stdlib os.readlink result, `None` on `OSError`/`ValueError`; covers symlinks and
  Windows junctions; a leading `\\?\` that Windows adds to junction targets
  is stripped before comparing). Rules, first match wins:
  1. `link` set and `os.path.normpath(os.path.join(t.parent, link)) ==
     os.path.normpath(s)`: if `s` exists -> current, nothing; else problem
     `<target>: dangling link, no host file at <source>`. Never deleted.
  2. `link` set, points elsewhere -> problem
     `<target>: links to <link>, expected <source>; skipped`.
  3. `t` exists -> problem `<target>: exists and is not a link; skipped`.
  4. `s` missing -> problem `<target>: no host file at <source>`.
  5. `apply` false -> problem `<target>: link missing; run 'dot materialize'`.
  6. Else create `t.parent` (`mkdir(parents=True, exist_ok=True)`) and link to
     the absolute `s`: POSIX `os.symlink(s, t, target_is_directory=s.is_dir())`;
     Windows (`os.name == "nt"`) dirs via `_winapi.CreateJunction(str(s), str(t))`,
     files via `os.symlink`; an `OSError` from a Windows file symlink -> problem
     `<target>: symlink refused; enable Developer Mode`. Any other `OSError`
     -> problem `<target>: <exc>`. Success -> change `linked <target>`.
  No copy or hardlink fallback. Nothing is ever deleted or overwritten.

### Capability: Git hooks

#### Feature: Install hooks
- **Description**: Write the three relink hooks into the configured hooks dir.
- **Inputs**: `hooks_dir: Path`.
- **Outputs**: change lines `installed hook <name>`.
- **Behavior**: for each of `post-checkout`, `post-merge`, `post-rewrite`: when
  the file is missing, write `HOOK_SCRIPT` with
  `atomic_write_text(path, HOOK_SCRIPT, mode=0o755)`; an existing file is left
  untouched, even when it differs. `HOOK_SCRIPT` is exactly:

```python
#!/usr/bin/env python3
# Installed by dot: relink host-specific config after checkout, merge, rewrite.
import os
import shutil
import subprocess
import sys

dot = shutil.which("dot")
if dot is None:
    print("dot hook: 'dot' not found, host links not refreshed", file=sys.stderr)
else:
    env = {**os.environ, "BUVIS_AUTO_UPDATE": "false"}
    subprocess.run([dot, "materialize", "--hook"], check=False, env=env)
sys.exit(0)
```

### Capability: Commands (CLI, hook, TUI share them)

#### Feature: `dot materialize [--hook]`
- **Description**: Reconcile links with `apply=True`; outside hook mode also
  install missing hooks into the git core.hooksPath dir when it is set.
- **Inputs**: `--hook` flag.
- **Outputs**: `CommandResult(success=True, info=changes, warnings=problems)`;
  nothing printed when both are empty.
- **Behavior**: `--hook` skips hook install and makes no git call (git sets
  GIT_DIR in a hook's environment). Hook mode exits 0 always. Hooks dir comes from
  `cfg config core.hooksPath` with `~` expanded; unset -> skip install silently.

#### Feature: Link status in `dot status` and TUI
- **Description**: Report link problems without changing anything.
- **Behavior**: `CommandLinkStatus.execute()` returns
  `CommandResult(success=True, warnings=problems)` from `apply=False`.
  `CommandStatus.execute` appends those warnings before its empty check. The
  TUI status bar appends `  <n> link problem(s)` (bold yellow) when n > 0, and
  key `L` runs `CommandMaterialize` and shows its info+warnings lines in the
  diff pane (`Host links current` when both are empty), then refreshes.

## Structural Decomposition

### Repository Structure

```
src/tools/dot/
├── hostlinks/
│   ├── __init__.py
│   ├── manifest.py        # Parse manifest
│   ├── linker.py          # Reconcile links
│   └── hooks.py           # Install hooks
├── commands/
│   ├── materialize/{__init__,materialize}.py
│   ├── links/{__init__,links}.py
│   └── status/status.py   # + link warnings
├── git/service.py         # + hooks_path()
├── tui/app.py             # pass dotfiles_root to MainScreen
├── tui/screens/main.py    # status bar count, key L
├── tui/widgets/status_bar.py
└── cli.py                 # materialize command
```

### Module: hostlinks
- **Maps to capability**: Manifest, Linking, Git hooks
- **Responsibility**: Pure filesystem logic, no git, no UI.
- **Exports**: `MANIFEST_PATH` (`".config/buvis/host-links"`), `HostLink`
  (frozen dataclass `target: str`, `source: str`), `parse_manifest(text)`,
  `read_manifest(root)`, `reconcile_links(root, *, apply)`, `HOOK_NAMES`,
  `HOOK_SCRIPT`, `install_hooks(hooks_dir)`.
- New symbols: `hostlinks`, `MANIFEST_PATH`, `HostLink`, `parse_manifest`, `read_manifest`, `reconcile_links`, `_read_link`, `HOOK_NAMES`, `HOOK_SCRIPT`, `install_hooks`

### Module: commands
- **Maps to capability**: Commands
- **Responsibility**: `CommandResult` wrappers used by CLI, hook and TUI.
- **Exports**: `CommandMaterialize(shell, dotfiles_root, *, install_hooks=True)`,
  `CommandLinkStatus(dotfiles_root)`; `DotGitService.hooks_path() -> Path | None`.
- New symbols: `CommandMaterialize`, `CommandLinkStatus`, `hooks_path`, `materialize`, `links`

## Dependency Graph

### Foundation Layer (Phase 0)
- **hostlinks.manifest**: no dependencies.

### Core Layer (Phase 1)
- **hostlinks.linker**: depends on [hostlinks.manifest]
- **hostlinks.hooks**: depends on [`pybase.filesystem.atomic_write`]

### Integration Layer (Phase 2)
- **commands.materialize / commands.links**: depend on [linker, hooks, git.service]
- **cli, commands.status, tui**: depend on [commands.materialize, commands.links]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Manifest parsing.

**Tasks**:
- [ ] `hostlinks/manifest.py` per "Parse manifest" (no deps) - Acceptance:
  `uv run pytest tests/tools/dot/test_hostlinks_manifest.py` passes, with one
  test per reason string plus comments/blank lines and missing file.

**Exit Criteria**: manifest tests green.

### Phase 1: Core
**Goal**: Linking and hook install.

**Tasks**:
- [ ] `hostlinks/linker.py` per "Reconcile links" (depends on: Phase 0) -
  Acceptance: `uv run pytest tests/tools/dot/test_hostlinks_linker.py` passes;
  covers file link, dir link, rerun returns `([], [])`, real-file target bytes
  unchanged, link elsewhere, dangling link kept, missing source creates
  nothing, `apply=False` creates nothing, Windows dir -> junction call and
  Windows file `OSError` -> Developer Mode message (both via monkeypatched
  `os.name`, `os.symlink` and a patched junction function).
- [ ] `hostlinks/hooks.py` per "Install hooks" (no deps) - Acceptance:
  `uv run pytest tests/tools/dot/test_hostlinks_hooks.py` passes; missing hooks
  written with mode 0o755, existing hook bytes unchanged, and running the
  installed hook as `[sys.executable, <hook path>]` with `PATH` set to an
  empty temp dir exits 0 and prints the not-found line.

**Exit Criteria**: linker and hook tests green.

### Phase 2: Integration
**Goal**: Same command classes behind CLI, hook and TUI.

**Tasks**:
- [ ] `DotGitService.hooks_path()`, `CommandMaterialize`, `CommandLinkStatus`,
  `dot materialize [--hook]` in `cli.py` (depends on: Phase 1) - Acceptance:
  `uv run pytest tests/tools/dot/test_materialize.py tests/tools/dot/test_link_status.py`
  passes, including: hook mode makes no `shell.exe` call; unset hooksPath
  installs nothing; temp-`$HOME` CLI run via `CliRunner` with `DOTFILES_ROOT`
  set creates both links and a second run has empty output.
- [ ] `CommandStatus` appends link warnings; `DotApp` passes `dotfiles_root`
  to `MainScreen`; status bar count; key `L` (depends on: previous task) -
  Acceptance: new tests in `tests/tools/dot/test_status.py`,
  `tests/tools/dot/test_status_bar.py` and `tests/tools/dot/test_tui_app.py`
  pass (status shows the link warning; bar shows `1 link problem(s)`; `L`
  shows `linked <target>`); `uv run pytest -k "status or tui"` in
  `tests/tools/dot` passes with no edits to existing tests.
- [ ] Docs: `docs/source/tools/dot.rst` and `README.md` describe the manifest
  format, `dot materialize`, the hooks and the Windows Developer Mode note
  (depends on: previous task) - Acceptance: `rg -n "host-links" docs/source/tools/dot.rst README.md`
  finds both files.

**Exit Criteria**: `uv run pytest -m dot` and `uv run mypy src/tools/dot` pass.

## Test Strategy

### Critical Scenarios
- **Happy path**: file + dir entries, sources present -> two `linked` lines;
  rerun -> no output.
- **Edge case**: target is a tracked real file -> warning, bytes unchanged.
- **Edge case**: source removed after linking -> dangling warning, link kept.
- **Error case**: invalid manifest line -> `host-links:<n>: <reason>`, other
  lines still processed.
- **Error case**: `dot` missing on PATH in a hook -> stderr line, exit 0.

## Risks

- **Hook files land in a tracked dir**: dot writes them only when missing, so
  the first host commits them and later hosts get them by checkout; dot never
  rewrites them, so a later `HOOK_SCRIPT` change needs a manual edit.
- **`python3` absent on Windows**: Git for Windows runs hooks through its sh;
  the shebang needs `python3` on PATH. Accepted; hook failure never blocks git.
- **Glean settling (M13)**: host config outside gems (glean link_roots), not an
  autopilot task; done by hand after 00090 ships.
