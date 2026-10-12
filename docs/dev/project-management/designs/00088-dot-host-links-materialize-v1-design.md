# Design: 00088 dot host links (manifest, materialize, hooks, link status)

PRD: `docs/dev/project-management/prds/wip/00088-dot-host-links-materialize-v1.md`

## Architecture fit

- Lands entirely in `src/tools/dot/`. New pure-filesystem package `dot/hostlinks/`
  (no git, no UI, no console) sits beside `dot/git/` as a second domain module.
- Command layer (`dot/commands/<name>/`) wraps it in `CommandResult` classes, per
  the repo's CommandResult discipline (no console/sys.exit in commands).
- One action, one implementation: CLI (`dot materialize`), the git hook
  (`dot materialize --hook`), `dot status` and the TUI (`L`, status bar) all
  drive `CommandMaterialize` / `CommandLinkStatus`. The TUI reuses its existing
  `DotGitService` instance (the seam from PRD 00053) instead of building a second one.
- Persistence of hook files uses `buvis.pybase.filesystem.atomic_write_text`
  (atomic-persistence invariant). Links are created with `os.symlink` /
  junctions, never by copy.

## Module placement

New files:

- `src/tools/dot/hostlinks/__init__.py` - re-exports + `__all__`.
- `src/tools/dot/hostlinks/manifest.py` - `MANIFEST_PATH`, `HostLink`, `parse_manifest`, `read_manifest`.
- `src/tools/dot/hostlinks/linker.py` - `reconcile_links`, `_read_link`, `_create_junction`.
- `src/tools/dot/hostlinks/hooks.py` - `HOOK_NAMES`, `HOOK_SCRIPT`, `install_hooks`.
- `src/tools/dot/commands/materialize/__init__.py`, `materialize.py` - `CommandMaterialize`.
- `src/tools/dot/commands/links/__init__.py`, `links.py` - `CommandLinkStatus`.
- Tests: `tests/tools/dot/test_hostlinks_manifest.py`, `test_hostlinks_linker.py`,
  `test_hostlinks_hooks.py`, `test_materialize.py`, `test_link_status.py`.

Edits:

- `src/tools/dot/git/service.py` - add `DotGitService.hooks_path()`.
- `src/tools/dot/commands/status/status.py` - append link warnings.
- `src/tools/dot/cli.py` - `materialize` command.
- `src/tools/dot/tui/app.py` - pass `dotfiles_root` to `MainScreen`.
- `src/tools/dot/tui/screens/main.py` - `dotfiles_root` kwarg, link count, `L` binding.
- `src/tools/dot/tui/widgets/status_bar.py` - `link_problems` kwarg.
- Tests appended (new test functions only) in `tests/tools/dot/test_status.py`,
  `test_status_bar.py`, `test_tui_app.py`.
- Docs: `docs/source/tools/dot.rst`, `README.md`.

## Interfaces & contracts

### `dot/hostlinks/manifest.py`

```python
MANIFEST_PATH = ".config/buvis/host-links"

@dataclass(frozen=True)
class HostLink:
    target: str  # $HOME-relative POSIX path, stripped
    source: str  # $HOME-relative POSIX path, stripped

def parse_manifest(text: str) -> tuple[list[HostLink], list[str]]: ...
def read_manifest(root: Path) -> tuple[list[HostLink], list[str]]: ...
```

`parse_manifest` rules, per line (1-based `lineno` over `text.splitlines()`):

1. `stripped = line.strip()`; skip when empty or `stripped.startswith("#")`.
2. No `=>` in the line -> error `host-links:<lineno>: missing '=>'`.
3. `target, source = (part.strip() for part in line.split("=>", 1))`.
4. Check target, then source; first failing check wins for the line:
   - `""` -> `empty path`
   - absolute -> `absolute path`, where absolute means
     `PurePosixPath(s).is_absolute() or PureWindowsPath(s).is_absolute() or PureWindowsPath(s).drive != "" or PureWindowsPath(s).root != "" or s.startswith("~")`
     (the `root` term is stricter than the PRD on purpose: `\outside` has no
     drive and is not `is_absolute()` on Windows, yet `root / "\outside"`
     escapes to the drive root; it is reported as `absolute path`)
   - `".." in PurePosixPath(s).parts or ".." in PureWindowsPath(s).parts` -> `'..' not allowed`
5. `target == source` -> `target equals source`.
6. `target` already seen on an earlier valid line -> `duplicate target <target>`.
7. Otherwise append `HostLink(target, source)`.

Every error string is exactly `f"host-links:{lineno}: {reason}"`. Bad lines are
skipped; later lines are still parsed.

`read_manifest(root)`: reads `root / MANIFEST_PATH` as UTF-8.
`FileNotFoundError` -> `([], [])`. Any other `OSError` / `UnicodeDecodeError`
-> `([], [f"host-links: {exc}"])`. Otherwise `parse_manifest(text)`.

### `dot/hostlinks/linker.py`

```python
def _read_link(path: Path) -> str | None:
    """os.readlink(path) with a leading '\\\\?\\' stripped; None on OSError/ValueError."""

def _create_junction(source: str, target: str) -> None:
    """importlib.import_module("_winapi").CreateJunction(source, target)."""

def reconcile_links(root: Path, *, apply: bool) -> tuple[list[str], list[str]]: ...
```

`_create_junction` imports `_winapi` via `importlib.import_module` so mypy on
non-Windows hosts needs no suppression, and tests patch
`dot.hostlinks.linker._create_junction`.

`reconcile_links`: first `root = Path(os.path.abspath(root))` (absolute, no
symlink resolution, so a relative `DOTFILES_ROOT` still yields absolute link
destinations); then `entries, errors = read_manifest(root)`;
`changes: list[str] = []`; `problems = list(errors)` (manifest errors first).
For each entry: `t = root / entry.target`, `s = root / entry.source`,
`link = _read_link(t)`. Rules, first match wins (`<target>`/`<source>` are the
manifest strings, `<link>` the raw readlink value after prefix strip):

1. `link is not None and os.path.normpath(os.path.join(t.parent, link)) == os.path.normpath(s)`:
   `s.exists()` -> nothing; else problem `<target>: dangling link, no host file at <source>`.
2. `link is not None` -> problem `<target>: links to <link>, expected <source>; skipped`.
3. `t.exists()` -> problem `<target>: exists and is not a link; skipped`.
4. `not s.exists()` -> problem `<target>: no host file at <source>`.
5. `not apply` -> problem `<target>: link missing; run 'dot materialize'`.
6. Create, inside one `try`:
   - `t.parent.mkdir(parents=True, exist_ok=True)`
   - `os.name == "nt" and s.is_dir()` -> `_create_junction(str(s), str(t))`
   - `os.name == "nt"` (file) -> `os.symlink(s, t)`; `OSError` -> problem
     `<target>: symlink refused; enable Developer Mode`
   - POSIX -> `os.symlink(s, t, target_is_directory=s.is_dir())`
   - any other `OSError` (POSIX, junction, mkdir) -> problem `<target>: <exc>`
   - success -> change `linked <target>`

`s` is absolute because `reconcile_links` makes `root` absolute with
`os.path.abspath` on entry (`DOTFILES_ROOT` may be relative; `cli.py:_dotfiles_root`
passes it through unchanged). Nothing is ever deleted,
overwritten, copied or hardlinked.

### `dot/hostlinks/hooks.py`

```python
HOOK_NAMES: tuple[str, ...] = ("post-checkout", "post-merge", "post-rewrite")
HOOK_SCRIPT: str  # exactly the PRD's script text, trailing newline included

def install_hooks(hooks_dir: Path) -> list[str]: ...
```

`install_hooks`: `hooks_dir.mkdir(parents=True, exist_ok=True)`; for each name
in `HOOK_NAMES` whose `hooks_dir / name` does not exist (`not path.exists() and not path.is_symlink()`):
`atomic_write_text(path, HOOK_SCRIPT, mode=0o755)` and collect
`installed hook <name>`. Existing files are never read or written. Returns the
collected lines in `HOOK_NAMES` order. `OSError` propagates (caller handles).

### `dot/hostlinks/__init__.py`

`__all__ = ["HOOK_NAMES", "HOOK_SCRIPT", "MANIFEST_PATH", "HostLink", "install_hooks", "parse_manifest", "read_manifest", "reconcile_links"]`

### `DotGitService.hooks_path`

```python
def hooks_path(self) -> Path | None:
    """Return the configured core.hooksPath, or None when unset."""
```

`err, out = self.shell.exe("cfg config core.hooksPath", self.wd)`; `err` or
blank `out` -> `None`. Else `p = Path(os.path.expanduser(out.strip()))`;
relative `p` -> `self.wd / p` (git resolves a relative hooksPath against the
work-tree root, where hooks run). Return `p`.

### `CommandMaterialize` (`dot/commands/materialize/materialize.py`)

```python
class CommandMaterialize:
    def __init__(
        self,
        shell: ShellAdapter,
        dotfiles_root: str,
        *,
        install_hooks: bool = True,
        git_service: DotGitService | None = None,
    ) -> None: ...
    def execute(self) -> CommandResult: ...
```

`execute`:

1. `changes, problems = reconcile_links(Path(self.dotfiles_root), apply=True)`.
2. If `install_hooks`: `service = git_service or DotGitService(shell, dotfiles_root)`
   (constructed lazily inside `execute`, never in hook mode, because the
   `DotGitService` constructor itself runs a git call); `hooks_dir = service.hooks_path()`;
   when not `None`: `changes = [*changes, *install_hooks(hooks_dir)]`, with
   `OSError` -> `problems = [*problems, f"hooks: {exc}"]`.
3. Return `CommandResult(success=True, info=changes, warnings=problems)`.

Never returns `success=False`; no `output`, so the CLI prints nothing when both
lists are empty. `install_hooks=False` makes zero `shell.exe` calls.

### `CommandLinkStatus` (`dot/commands/links/links.py`)

```python
class CommandLinkStatus:
    def __init__(self, dotfiles_root: str) -> None: ...
    def execute(self) -> CommandResult:
        # _changes, problems = reconcile_links(Path(dotfiles_root), apply=False)
        # return CommandResult(success=True, warnings=problems)
```

`__init__.py` files export `CommandMaterialize` / `CommandLinkStatus` with `__all__`,
matching `commands/push/__init__.py`.

### `CommandStatus` edit

`__init__` stores `self.dotfiles_root = dotfiles_root`. In `execute`, after the
ahead/behind warnings and before the `if not info and not warnings` check:
`warnings.extend(CommandLinkStatus(self.dotfiles_root).execute().warnings)`.
(The hide-secrets early failure return is unchanged.)

### CLI

```python
@cli.command("materialize", help="Link host-specific config listed in host-links")
@click.option("--hook", is_flag=True, help="Run from a git hook: skip hook install and git calls")
def materialize(hook: bool) -> None:
    from dot.commands.materialize.materialize import CommandMaterialize

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(
        CommandMaterialize(shell=shell, dotfiles_root=_dotfiles_root(), install_hooks=not hook).execute()
    )
```

Exit code is always 0 (result is always success).

### TUI

- `DotApp.on_mount`: `MainScreen(self._git_ops, confirm_revert=self._confirm_revert, dotfiles_root=self._dotfiles_root)`;
  `DotApp.__init__` stores `self._dotfiles_root = dotfiles_root`.
- `MainScreen.__init__(self, git_ops, *, confirm_revert: bool = True, dotfiles_root: str | None = None)`;
  stores `self._dotfiles_root`.
- `MainScreen.refresh_status`: `link_problems = len(CommandLinkStatus(self._dotfiles_root).execute().warnings) if self._dotfiles_root else 0`;
  pass `link_problems=link_problems` to `StatusBar.update_info`.
- `StatusBar.update_info(self, info: BranchInfo, error: str | None = None, link_problems: int = 0)`;
  `_render_info` appends `f"  {n} link problem(s)"` with style `"bold yellow"`
  when `n > 0`, after the secrets segment and before the error segment.
- New binding `Binding("L", "materialize", "Links", show=True)`.
  `action_materialize`: when `self._dotfiles_root` is `None`, return without
  action; otherwise
  `result = CommandMaterialize(self._git_ops.shell, self._dotfiles_root, git_service=self._git_ops).execute()`;
  `self._show_message("\n".join([*result.info, *result.warnings]) or "Host links current")`;
  then `self.refresh_status()`.

## Data flow

```
host-links (tracked text) --read_manifest--> HostLink[] + line errors
   --reconcile_links(root, apply)--> (changes, problems)
      apply=True : CommandMaterialize --+ install_hooks(hooks_path())--> CommandResult(info, warnings)
                                         --> CLI console.report_result | TUI diff pane
      apply=False: CommandLinkStatus --> CommandResult(warnings)
                                         --> CommandStatus warnings | TUI status bar count
git checkout/merge/rewrite --> hook script --> `dot materialize --hook` (BUVIS_AUTO_UPDATE=false)
```

## Reuse inventory

- `buvis.pybase.filesystem.atomic_write_text(path, data, mode=0o755)` - hook file writes.
- `buvis.pybase.result.CommandResult(success, info, warnings)` - command returns.
- `ConsoleAdapter.report_result` - prints info as success, warnings as warning,
  nothing when both empty and no `output` (checked `console.py:242`).
- `DotGitService.shell` / `.wd` and the `cfg` alias - `hooks_path` git call.
- `MainScreen._show_message` - writes text to the diff pane.
- `tests/tools/dot/conftest.py::dotfiles_root` fixture (tmp root + `DOTFILES_ROOT` env).
- Symlink/readlink/junction/hooksPath helpers: nothing found, greps tried:
  `rg "symlink|readlink|CreateJunction|hooksPath|core.hooks" src --type py`
  (hits only in backup/muc/bim for archive and confinement, not link creation);
  control term `atomic_write` proved the search works.

## Alternatives considered

1. **Smallest diff: CLI-only `dot materialize`, no TUI/status integration.**
   Rejected: violates the all-interface rule and the PRD's link-status feature.
2. **`CommandMaterialize` always builds its own `DotGitService` (exact PRD
   signature).** Rejected: the TUI already holds one (tests mock it), and a
   second instance repeats the fetch-refspec git call; the optional
   `git_service` kwarg costs one parameter and keeps one implementation.
3. **Chosen:** pure `hostlinks` package + two thin commands + optional
   `git_service` injection. Extra size over (1) buys status/TUI parity.

Also rejected: copy/hardlink fallback on Windows (PRD forbids), and reading the
TUI root from `git_ops.dotfiles_root` (a `MagicMock` in every TUI test; explicit
`dotfiles_root` is clearer).

## Risks & edge cases

- `t.exists()` follows links; rules 1-2 catch every link first, so a dangling
  link never reaches rule 3.
- macOS `/var` -> `/private/var`: comparison uses `normpath`, not `resolve`, and
  links are written to the same unresolved absolute `s`, so reruns match.
- Windows junction targets come back as `\\?\C:\...`; stripped in `_read_link`.
- Relative `core.hooksPath` resolved against work-tree root.
- `CommandStatus` now touches the filesystem; with no manifest it is a single
  missing-file read.
- Next changes: 00090 (localize + pull rescue) will reuse `read_manifest` and
  `_read_link`; 00091 (self-heal + setup) will call `CommandMaterialize`. Keep
  `reconcile_links` return shape stable; nothing here boxes those in.

## Test strategy outline

- Manifest: one test per reason string, comment/blank lines, missing file,
  mixed good/bad lines still parse; `\outside` and `C:x` report `absolute path`.
- Linker: relative root (`monkeypatch.chdir(tmp)`, root `Path("home")`) creates
  an absolute link and the rerun returns `([], [])`.
- Linker (tmp root): file link, dir link, rerun `([], [])`, real-file target bytes
  unchanged, link elsewhere, dangling kept, missing source creates nothing,
  `apply=False` creates nothing; Windows via `monkeypatch.setattr(os, "name", "nt")`,
  patched `os.symlink` and `dot.hostlinks.linker._create_junction`.
- Hooks: mode `0o755`, existing bytes unchanged, run installed hook with
  `[sys.executable, hook]` and `PATH` = empty tmp dir -> exit 0, not-found line on stderr.
- Commands: hook mode zero `shell.exe` calls; `hooks_path()` None -> no install;
  `CliRunner` temp-`$HOME` run creates both links, second run empty output.
- Status/TUI: link warning in `dot status`; bar text `1 link problem(s)`; `L`
  shows `linked <target>`; existing tests untouched.

## Review log

- non-blocker (d1): CliRunner test with real `DotGitService` reads global/system git config; a global `core.hooksPath` would get hooks written. Patch `DotGitService`/`hooks_path` in that test or isolate git config.
- non-blocker (d1): `monkeypatch.setattr(os, "name", "nt")` breaks `Path(...)` construction on 3.11/3.12; prefer a `_is_windows()` seam in `linker.py` to patch.
- non-blocker (d1): `exists()`/`is_dir()` outside the try can raise `PermissionError`; wrap each entry's evaluation in `try/except OSError` -> `<target>: <exc>`.
- non-blocker (d1): append `L` as the last `MainScreen.BINDINGS` entry so snapshot footers stay unchanged.
- question (d1): should an existing non-dot hook file be reported (it silently stops relinking)?
- question (d1): `install_hooks` kwarg shadows the imported `install_hooks` function; store as `self._install_hooks` and alias the import.
- dispatch 1 (claude): cardinal-sin 0, blocker 0, non-blocker 4, question 2
- dispatch 2: codex sandbox could not read files (`sandbox_apply: Operation not permitted`); re-run once with files inlined in the prompt (engagement retry, same reviewer).
- blocker (d2, fixed): relative `DOTFILES_ROOT` produced relative link destinations; `reconcile_links` now applies `os.path.abspath` to `root`.
- blocker (d2, fixed): Windows rooted paths (`\outside`) passed validation; absolute check now includes `PureWindowsPath(s).root != ""`.
- non-blocker (d2): check-then-`atomic_write_text` (`os.replace`) can clobber a hook created concurrently between check and write.
- non-blocker (d2): PRD `HOOK_SCRIPT` lets an `OSError` from `subprocess.run` (unlaunchable `dot`) escape before `sys.exit(0)`; script text is PRD-fixed, so kept verbatim.
- dispatch 2 (codex): cardinal-sin 0, blocker 2, non-blocker 2, question 0
- non-blocker (d3): `_read_link` strip of `\\?\` turns `\\?\UNC\server\share` into a relative-looking path; map `\\?\UNC\` to `\\` first.
- non-blocker (d3): an `OSError` on the second hook loses the first hook's `installed hook` line.
- non-blocker (d3): embedded NUL in a manifest path raises `ValueError` during fs calls; catch `ValueError` with `OSError` per entry.
- dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 3, question 0
