# PRD 00090: dot host links: localize and pull rescue — Implementation Design

**PRD**: `docs/dev/project-management/prds/backlog/00090-dot-host-links-localize-pull-rescue-v1.md`
**Prerequisite**: PRD 00088 (manifest, `reconcile_links`, `CommandMaterialize`) — shipped
**Date**: 2026-10-13

---

## Executive Summary

This design covers the implementation of `dot localize` (convert a tracked file to host-specific) and pull rescue (protect host-local files when another host's localize-commit arrives). The PRD decomposes into three phases: Foundation (primitives), Core (rescue logic + localize command), and Integration (CommandPull with rescue, CLI prompts, TUI modal).

---

## Phase 0: Foundation

### 0.1 DotGitService Additions

**Module**: `src/tools/dot/git/service.py`

All new methods follow the existing pattern: `shlex.quote` for path arguments, `(err, out) = self.shell.exe(cmd, self.wd)` style, error text or `""` on success.

#### 0.1.1 `fetch() -> str`

```python
def fetch(self) -> str:
    """Fetch from origin.

    Returns:
        Error text on failure, empty string on success.
    """
    err, _out = self.shell.exe("cfg fetch", self.wd)
    return err or ""
```

**Command**: `cfg fetch`
**Returns**: `err` (the stderr/exception text) on failure, `""` on success.

#### 0.1.2 `has_upstream() -> bool`

```python
def has_upstream(self) -> bool:
    """Check if an upstream tracking branch is configured.

    Returns:
        True if @{u} resolves, False otherwise.
    """
    err, _out = self.shell.exe("cfg rev-parse --verify --quiet @{u}", self.wd)
    return not err
```

**Command**: `cfg rev-parse --verify --quiet @{u}`
**Returns**: `True` if the command succeeds (exit 0), `False` if it fails (exit ≠ 0).

#### 0.1.3 `show_upstream_file(path: str) -> str | None`

```python
def show_upstream_file(self, path: str) -> str | None:
    """Read a file's content from the upstream branch.

    Args:
        path: File path relative to the work-tree root.

    Returns:
        The file content, or None if the file does not exist at @{u}.
    """
    err, out = self.shell.exe(f"cfg show @{{u}}:{shlex.quote(path)}", self.wd)
    if err:
        return None
    return out
```

**Command**: `cfg show @{u}:<shlex-quoted-path>`
**Returns**: File content as string on success, `None` on any error (file missing, no upstream, etc.).

#### 0.1.4 `upstream_deleted_paths() -> list[str]`

```python
def upstream_deleted_paths(self) -> list[str]:
    """List paths deleted in commits between HEAD and upstream.

    Returns:
        Deleted paths, or empty list if diff fails or no upstream.
    """
    err, out = self.shell.exe(
        "cfg diff --name-only --no-renames -z --diff-filter=D HEAD...@{u}",
        self.wd,
    )
    if err:
        return []
    # NUL-separated output; filter empty strings from trailing NUL
    return [p for p in out.split("\0") if p]
```

**Command**: `cfg diff --name-only --no-renames -z --diff-filter=D HEAD...@{u}`
- `--no-renames`: Prevents a delete from pairing with an add as a rename.
- `-z`: NUL-separated output, no quoting of special characters.
- `--diff-filter=D`: Only deleted files.

**Returns**: List of deleted paths; empty list on error or no upstream.

#### 0.1.5 `untrack(path: str) -> CommandResult`

```python
def untrack(self, path: str) -> CommandResult:
    """Remove a path from the index without touching the work-tree.

    Args:
        path: Path to untrack; supports directories (recursive).

    Returns:
        The outcome of the untrack command.
    """
    err, _out = self.shell.exe(
        f"cfg rm -r --cached --quiet -- {shlex.quote(path)}",
        self.wd,
    )
    if err:
        return CommandResult(success=False, error=err)
    return CommandResult(success=True)
```

**Command**: `cfg rm -r --cached --quiet -- <shlex-quoted-path>`
- `-r`: Recursive for directories.
- `--cached`: Index only, disk untouched.
- `--quiet`: Suppress per-file output.
- `--`: End-of-options guard.

**Returns**: `CommandResult(success=True)` on success, `CommandResult(success=False, error=<err>)` on failure.

---

### 0.2 manifest.append_entry

**Module**: `src/tools/dot/hostlinks/manifest.py`

```python
from buvis.pybase.filesystem import atomic_write_text
from pathlib import Path
from dot.hostlinks.manifest import MANIFEST_PATH, HostLink


def append_entry(root: Path, link: HostLink) -> None:
    """Append a host-link entry to the manifest atomically.

    Creates the manifest file and parent directories if missing. Ensures a
    trailing newline before appending the entry when the existing content
    lacks one.

    Args:
        root: The dotfiles root directory.
        link: The host link to append.

    Raises:
        OSError: If the write fails.
    """
    manifest_path = root / MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        existing = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""

    entry_line = f"{link.target} => {link.source}\n"

    if existing and not existing.endswith("\n"):
        new_content = existing + "\n" + entry_line
    else:
        new_content = existing + entry_line

    atomic_write_text(manifest_path, new_content)
```

**Semantics**:
1. Creates `.config/buvis/` parent directories if missing (`mkdir(parents=True, exist_ok=True)`).
2. Reads existing content; treats `FileNotFoundError` as empty string.
3. Appends `<target> => <source>\n`.
4. If existing content lacks trailing newline, inserts one first.
5. Uses `atomic_write_text` (tempfile + fsync + os.replace) per AGENTS.md atomic-persistence invariant.

**Export**: Add to `__all__` in `hostlinks/__init__.py`.

---

### 0.3 ConsoleAdapter.choose

**Module**: `src/lib/buvis/pybase/adapters/console/console.py`

```python
from rich.prompt import Prompt

class ConsoleAdapter:
    # ... existing methods ...

    def choose(self, question: str, choices: list[str], default: str | None = None) -> str:
        """Prompt the user to select from a list of choices.

        Args:
            question: The prompt text.
            choices: Valid choices.
            default: Pre-selected default value.

        Returns:
            The user's selection.
        """
        return Prompt.ask(question, choices=choices, default=default)
```

**Wiring**: Directly delegates to `rich.prompt.Prompt.ask(question, choices=choices, default=default)`.

**Returns**: The user's selected string from `choices`.

---

## Phase 1: Core

### 1.1 hostlinks/rescue.py

**Module**: `src/tools/dot/hostlinks/rescue.py`

#### 1.1.1 Resolution StrEnum

```python
from __future__ import annotations

import enum


class Resolution(enum.StrEnum):
    """Resolution choice for a host-link collision."""

    KEEP_SOURCE = "keep-source"
    KEEP_TARGET = "keep-target"
    CANCEL = "cancel"
```

**Note**: `StrEnum` requires Python 3.11+, which the project supports (3.11+).

#### 1.1.2 RescuePlan Dataclass

```python
import dataclasses
from dot.hostlinks.manifest import HostLink


@dataclasses.dataclass
class RescuePlan:
    """Plan for pre-merge rescue of host-link targets.

    Attributes:
        moves: Entries where target exists but source is missing.
        duplicates: Entries where target and source have identical bytes.
        collisions: Entries where target and source differ (or one is a dir).
        skipped: Reason rescue was skipped, or None if planned successfully.
        error: Error that prevented planning, or None.
    """

    moves: list[HostLink] = dataclasses.field(default_factory=list)
    duplicates: list[HostLink] = dataclasses.field(default_factory=list)
    collisions: list[HostLink] = dataclasses.field(default_factory=list)
    skipped: str | None = None
    error: str | None = None
```

#### 1.1.3 plan_rescue

```python
import filecmp
from pathlib import Path
from typing import TYPE_CHECKING

from dot.hostlinks.manifest import MANIFEST_PATH, HostLink, parse_manifest

if TYPE_CHECKING:
    from dot.git.service import DotGitService


def plan_rescue(root: Path, git_service: DotGitService) -> RescuePlan:
    """Plan the pre-merge rescue for host-link targets.

    Args:
        root: Dotfiles root directory.
        git_service: Initialized DotGitService (after fetch()).

    Returns:
        A RescuePlan describing what needs to happen.
    """
    if not git_service.has_upstream():
        return RescuePlan(skipped="pull rescue skipped: no upstream branch")

    # Get the upstream manifest
    upstream_text = git_service.show_upstream_file(MANIFEST_PATH)
    if upstream_text is None:
        upstream_text = ""

    upstream_links, _errors = parse_manifest(upstream_text)
    upstream_by_target = {link.target: link for link in upstream_links}

    # Get deleted paths from upstream
    deleted_paths = set(git_service.upstream_deleted_paths())

    moves: list[HostLink] = []
    duplicates: list[HostLink] = []
    collisions: list[HostLink] = []

    for deleted in deleted_paths:
        # Check if this deleted path is a target in the upstream manifest
        # or is under a target directory
        for upstream_target, upstream_link in upstream_by_target.items():
            if deleted == upstream_target or deleted.startswith(upstream_target + "/"):
                # This deletion affects this host-link entry
                target_path = root / upstream_link.target
                source_path = root / upstream_link.source

                # Skip if target is missing or already a link
                if not target_path.exists() or target_path.is_symlink():
                    continue

                # Classify based on source state
                if not source_path.exists():
                    # Source missing: this is a move
                    if upstream_link not in moves:
                        moves.append(upstream_link)
                elif target_path.is_file() and source_path.is_file():
                    # Both are files: compare bytes
                    if filecmp.cmp(target_path, source_path, shallow=False):
                        # Identical bytes: duplicate
                        if upstream_link not in duplicates:
                            duplicates.append(upstream_link)
                    else:
                        # Different bytes: collision
                        if upstream_link not in collisions:
                            collisions.append(upstream_link)
                else:
                    # At least one is a directory: collision
                    if upstream_link not in collisions:
                        collisions.append(upstream_link)
                break

    return RescuePlan(moves=moves, duplicates=duplicates, collisions=collisions)
```

**Classification Rules**:
1. **moves**: Target exists, source missing → move target to source.
2. **duplicates**: Both are regular files with `filecmp.cmp(t, s, shallow=False)` returning `True` → byte-identical, just unlink target.
3. **collisions**: Both exist but differ (different bytes, or one/both is a directory) → requires user choice.

#### 1.1.4 apply_rescue

```python
import shutil
from datetime import datetime, timezone

from buvis.pybase.result import CommandResult


def apply_rescue(
    root: Path,
    plan: RescuePlan,
    resolutions: dict[str, Resolution] | None = None,
) -> CommandResult:
    """Apply the rescue plan.

    Args:
        root: Dotfiles root directory.
        plan: The rescue plan from plan_rescue().
        resolutions: Resolution choices keyed by target for collisions.

    Returns:
        CommandResult with info lines describing actions taken.
    """
    if resolutions is None:
        resolutions = {}

    # Check for unresolved collisions or CANCEL
    unresolved = []
    for entry in plan.collisions:
        resolution = resolutions.get(entry.target)
        if resolution is None or resolution == Resolution.CANCEL:
            unresolved.append(entry.target)

    if unresolved:
        return CommandResult(
            success=False,
            error=f"pull stopped: unresolved host-link collision(s): {', '.join(unresolved)}",
        )

    # Generate backup path with UTC timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Pre-check: ensure no backup paths already exist
    for entry in plan.collisions:
        source_path = root / entry.source
        backup_path = source_path.parent / f"{source_path.name}.dot-{timestamp}"
        if backup_path.exists():
            return CommandResult(
                success=False,
                error=f"backup path already exists: {backup_path}",
            )

    info: list[str] = []

    # Apply moves: move target to source
    for entry in plan.moves:
        target_path = root / entry.target
        source_path = root / entry.source
        source_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target_path), str(source_path))
        info.append(f"rescued {entry.target} to {entry.source}")

    # Apply duplicates: just unlink target (source has identical bytes)
    for entry in plan.duplicates:
        target_path = root / entry.target
        if target_path.is_dir():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
        info.append(f"rescued {entry.target} to {entry.source}")

    # Apply collisions based on resolution
    for entry in plan.collisions:
        target_path = root / entry.target
        source_path = root / entry.source
        backup_path = source_path.parent / f"{source_path.name}.dot-{timestamp}"
        resolution = resolutions[entry.target]

        if resolution == Resolution.KEEP_SOURCE:
            # Keep source, backup target
            shutil.move(str(target_path), str(backup_path))
            info.append(f"kept {entry.source}, moved {entry.target} to {backup_path.name}")
        elif resolution == Resolution.KEEP_TARGET:
            # Backup old source, move target to source
            shutil.move(str(source_path), str(backup_path))
            shutil.move(str(target_path), str(source_path))
            info.append(
                f"kept {entry.target} as {entry.source}, moved old source to {backup_path.name}"
            )

    return CommandResult(success=True, info=info)
```

**Backup Path Format**: `<source>.dot-<UTC %Y%m%dT%H%M%SZ>`
Example: `.local/.zshrc.dot-20261013T211100Z`

**No-Byte-Loss Guarantees**:
1. **moves**: Original bytes moved to source.
2. **duplicates**: Source already has identical bytes; target unlinked.
3. **KEEP_SOURCE**: Target bytes moved to backup.
4. **KEEP_TARGET**: Old source bytes moved to backup, target bytes moved to source.
5. Nothing is ever deleted except byte-identical duplicates.

---

### 1.2 CommandLocalize

**Module**: `src/tools/dot/commands/localize/localize.py`

```python
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService
from dot.hostlinks.linker import _create_link
from dot.hostlinks.manifest import MANIFEST_PATH, HostLink, read_manifest, append_entry

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandLocalize:
    """Convert a tracked file or directory to a host-specific link."""

    def __init__(
        self,
        shell: ShellAdapter,
        dotfiles_root: str,
        path: str,
        source: str | None = None,
        *,
        git_service: DotGitService | None = None,
    ) -> None:
        """Initialize the localize command.

        Args:
            shell: Shell adapter for git commands.
            dotfiles_root: Path to the dotfiles root directory.
            path: Target path ($HOME-relative or absolute under dotfiles root).
            source: Optional source path; defaults to .local/<path>.
            git_service: Optional pre-initialized git service.
        """
        self._shell = shell
        self._root = Path(dotfiles_root)
        self._git_service = git_service or DotGitService(shell, dotfiles_root)

        # Normalize path to dotfiles-relative
        input_path = Path(path)
        if input_path.is_absolute():
            try:
                self._target = str(input_path.relative_to(self._root))
            except ValueError:
                # Path is not under dotfiles root
                self._target = path
        else:
            self._target = path

        # Default source is .local/<path>
        self._source = source if source is not None else f".local/{self._target}"

    def execute(self) -> CommandResult:
        """Execute the localize command.

        Returns:
            CommandResult with info lines on success, error on failure.
        """
        target_path = self._root / self._target
        source_path = self._root / self._source

        # --- Precondition checks (refuse, changing nothing) ---

        # Target must exist
        if not target_path.exists():
            return CommandResult(
                success=False,
                error=f"{self._target} does not exist",
            )

        # Target must not be a link
        if target_path.is_symlink():
            return CommandResult(
                success=False,
                error=f"{self._target} is already a link",
            )

        # Source must not exist
        if source_path.exists() or source_path.is_symlink():
            return CommandResult(
                success=False,
                error=f"{self._source} already exists",
            )

        # Target must not already be in manifest
        links, _errors = read_manifest(self._root)
        for link in links:
            if link.target == self._target:
                return CommandResult(
                    success=False,
                    error=f"{self._target} already listed in host-links manifest",
                )

        # Check git-secret files
        secrets = set(self._git_service.list_secrets())
        tracked = self._git_service.ls_files(self._target)
        for tracked_file in tracked:
            if tracked_file in secrets:
                return CommandResult(
                    success=False,
                    error=f"{tracked_file} is a git-secret file; localize refused",
                )

        # Validate using 00088 manifest rules (same validation as parse_manifest)
        # Target and source must be relative, no .., no absolute, not equal
        from dot.hostlinks.manifest import _validate_path

        problem = _validate_path(self._target) or _validate_path(self._source)
        if problem:
            return CommandResult(success=False, error=f"invalid path: {problem}")
        if self._target == self._source:
            return CommandResult(success=False, error="target equals source")

        # --- Mutation sequence with rollback ---

        info: list[str] = []
        was_tracked = bool(tracked)
        did_untrack = False
        did_move = False
        did_link = False

        try:
            # Step 1: Untrack (if tracked)
            if was_tracked:
                result = self._git_service.untrack(self._target)
                if not result.success:
                    return CommandResult(
                        success=False,
                        error=f"untrack failed: {result.error}",
                    )
                did_untrack = True
                info.append(f"untracked {self._target}")

            # Step 2: Move target to source
            source_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target_path), str(source_path))
            did_move = True
            info.insert(0, f"moved {self._target} to {self._source}")

            # Step 3: Create the link
            link_error = _create_link(source_path, target_path)
            if link_error:
                raise _LocalizeError(f"link creation failed: {link_error}")
            did_link = True
            info.append(f"linked {self._target}")

            # Step 4: Append entry to manifest
            new_link = HostLink(target=self._target, source=self._source)
            append_entry(self._root, new_link)

            # Step 5: Stage the manifest
            stage_result = self._git_service.stage(MANIFEST_PATH)
            if not stage_result.success:
                return CommandResult(
                    success=True,
                    info=info,
                    warnings=[
                        f"stage failed: {stage_result.error}; run 'dot add {MANIFEST_PATH}'"
                    ],
                )
            info.append(f"staged {MANIFEST_PATH}")

            return CommandResult(success=True, info=info)

        except _LocalizeError as exc:
            # Rollback in reverse order
            if did_link and target_path.is_symlink():
                target_path.unlink()
            if did_move:
                shutil.move(str(source_path), str(target_path))
            if did_untrack:
                self._git_service.unstage(self._target)
            return CommandResult(success=False, error=str(exc))

        except OSError as exc:
            # Rollback in reverse order
            if did_link and target_path.is_symlink():
                target_path.unlink(missing_ok=True)
            if did_move and source_path.exists():
                try:
                    shutil.move(str(source_path), str(target_path))
                except OSError:
                    pass
            if did_untrack:
                self._git_service.unstage(self._target)
            return CommandResult(success=False, error=str(exc))


class _LocalizeError(Exception):
    """Internal error for rollback control flow."""

    pass
```

**Refusal Preconditions** (exact error strings):
1. `"{target} does not exist"` — target missing
2. `"{target} is already a link"` — target is a symlink
3. `"{source} already exists"` — source exists or is a link
4. `"{target} already listed in host-links manifest"` — duplicate entry
5. `"{tracked_file} is a git-secret file; localize refused"` — any tracked file is a secret
6. `"invalid path: {problem}"` — validation failure (absolute, .., empty)
7. `"target equals source"` — same path

**Mutation Sequence** (ordered):
1. **Untrack** (if tracked): `DotGitService.untrack(target)` → `cfg rm -r --cached --quiet -- <path>`
2. **Move**: `shutil.move(target, source)` (creates source parent dirs first)
3. **Link**: `_create_link(source, target)` from linker.py
4. **Append**: `append_entry(root, HostLink(target, source))`
5. **Stage**: `DotGitService.stage(MANIFEST_PATH)`

**Rollback** (reverse order on failure):
- Step 5 failure: Does NOT rollback; returns success with warning: `"stage failed: {err}; run 'dot add .config/buvis/host-links'"`
- Step 4 failure: Remove link if created → move source back → unstage target
- Step 3 failure: Move source back → unstage target
- Step 2 failure: Unstage target (if step 1 ran)
- Step 1 failure: Return immediately, nothing changed

---

### 1.3 CLI: dot localize

**Module**: `src/tools/dot/cli.py`

```python
@cli.command("localize", help="Make a file or directory host-specific")
@click.argument("path")
@click.option("--to", "source", help="Source path (default: .local/<path>)")
def localize(path: str, source: str | None = None) -> None:
    from dot.commands.localize.localize import CommandLocalize

    shell = ShellAdapter(suppress_logging=True)
    console.report_result(
        CommandLocalize(
            shell=shell,
            dotfiles_root=_dotfiles_root(),
            path=path,
            source=source,
        ).execute()
    )
```

---

## Phase 2: Integration

### 2.1 Test Premise Guard

**CRITICAL**: Before editing `tests/tools/dot/test_pull.py`, verify the test count:

```bash
rg -c "def test_" tests/tools/dot/test_pull.py
# Expected output: 6
```

If the count differs from 6, **STOP** and report instead of rewriting tests.

The current 6 tests are:
1. `TestCommandPullInit.test_constructs_dot_git_service_with_shell_and_dotfiles_root`
2. `TestCommandPullInit.test_does_not_mutate_environment`
3. `TestCommandPullInit.test_does_not_call_shell_alias`
4. `TestCommandPullExecute.test_execute_calls_service_pull_with_no_passphrase_and_returns_success`
5. `TestCommandPullExecute.test_execute_returns_service_failure_passthrough`
6. `TestCommandPullExecute.test_execute_never_calls_shell_directly`

---

### 2.2 CommandPull Refactor

**Module**: `src/tools/dot/commands/pull/pull.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.commands.materialize.materialize import CommandMaterialize
from dot.git.service import DotGitService
from dot.hostlinks.rescue import Resolution, RescuePlan, apply_rescue, plan_rescue

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandPull:
    """Pull dotfiles with host-link rescue."""

    def __init__(
        self,
        shell: ShellAdapter,
        dotfiles_root: str,
        *,
        git_service: DotGitService | None = None,
    ) -> None:
        """Initialize the pull command.

        Args:
            shell: Shell adapter for git commands.
            dotfiles_root: Path to the dotfiles root directory.
            git_service: Optional pre-initialized git service.
        """
        self._shell = shell
        self._dotfiles_root = dotfiles_root
        self._root = Path(dotfiles_root)
        self.dot_git_service = git_service or DotGitService(shell, dotfiles_root)

    def plan(self) -> RescuePlan:
        """Fetch and plan the rescue.

        Returns:
            RescuePlan describing what needs to happen.
        """
        fetch_err = self.dot_git_service.fetch()
        if fetch_err:
            return RescuePlan(error=f"Fetch failed: {fetch_err}")

        return plan_rescue(self._root, self.dot_git_service)

    def execute(
        self,
        plan: RescuePlan | None = None,
        resolutions: dict[str, Resolution] | None = None,
        passphrase: str | None = None,
    ) -> CommandResult:
        """Execute the pull with rescue.

        Args:
            plan: Pre-computed rescue plan; computed fresh if None.
            resolutions: Collision resolutions keyed by target.
            passphrase: GPG passphrase for secret reveal.

        Returns:
            CommandResult with combined info/warnings from rescue, pull, and materialize.
        """
        if plan is None:
            plan = self.plan()

        if plan.error:
            return CommandResult(success=False, error=plan.error)

        # Apply rescue
        rescue_result = apply_rescue(self._root, plan, resolutions)
        if not rescue_result.success:
            return rescue_result

        rescued_sources = [e.source for e in plan.moves + plan.duplicates + plan.collisions]

        # Execute pull
        pull_result = self.dot_git_service.pull(passphrase=passphrase)
        if not pull_result.success:
            error = pull_result.error or "Pull failed"
            if rescued_sources:
                error += f"; rescued files are at: {', '.join(rescued_sources)}"
            return CommandResult(success=False, error=error)

        # Materialize links
        mat_result = CommandMaterialize(
            self._shell,
            self._dotfiles_root,
            install_hooks=False,
            git_service=self.dot_git_service,
        ).execute()

        # Merge results
        info = list(rescue_result.info) + list(mat_result.info)
        warnings = list(rescue_result.warnings) + list(mat_result.warnings)
        if plan.skipped:
            warnings.append(plan.skipped)

        return CommandResult(
            success=True,
            output=pull_result.output,
            info=info,
            warnings=warnings,
        )
```

---

### 2.3 CLI: dot pull with Prompts

**Module**: `src/tools/dot/cli.py`

```python
import sys


@cli.command("pull", help="Pull dotfiles and update submodules")
def pull() -> None:
    from dot.commands.pull.pull import CommandPull
    from dot.hostlinks.rescue import Resolution

    shell = ShellAdapter(suppress_logging=True)
    cmd = CommandPull(shell=shell, dotfiles_root=_dotfiles_root())

    # Plan rescue
    plan = cmd.plan()

    if plan.error:
        console.failure(plan.error)
        return

    # Handle collisions
    resolutions: dict[str, Resolution] = {}
    if plan.collisions:
        if sys.stdin.isatty():
            for entry in plan.collisions:
                console.warning(f"{entry.target} and {entry.source} both exist and differ")
                choice = console.choose(
                    "Resolve",
                    ["keep-source", "keep-target", "cancel"],
                    default="cancel",
                )
                resolutions[entry.target] = Resolution(choice)
        # Non-TTY: no prompts, execute will report unresolved collisions

    # Passphrase prompt
    if shell.is_command_available("git-secret"):
        console.info("GPG passphrase required to decrypt secret files")

    result = cmd.execute(plan=plan, resolutions=resolutions)
    console.report_result(
        result,
        on_failure=lambda r: console.failure(r.error or "Pull failed"),
    )
```

**TTY Behavior**:
- For each collision: print warning via `console.warning`, then prompt via `console.choose`
- Prompt: `"Resolve"` with choices `["keep-source", "keep-target", "cancel"]`, default `"cancel"`

**Non-TTY Behavior**:
- No prompts; `execute()` will return failure with unresolved collision message

---

### 2.4 TUI: RescueCollisionModal

**Module**: `src/tools/dot/tui/widgets/rescue_modal.py`

```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from dot.hostlinks.rescue import Resolution

__all__ = ["RescueCollisionModal"]


class RescueCollisionModal(ModalScreen[Resolution]):
    """Modal for resolving a host-link collision during pull."""

    CSS = """
    RescueCollisionModal {
        align: center middle;
    }
    RescueCollisionModal > Vertical {
        width: auto;
        max-width: 80%;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("s", "keep_source", "Keep source"),
        Binding("t", "keep_target", "Keep target"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, target: str, source: str) -> None:
        """Initialize the modal.

        Args:
            target: The target path in conflict.
            source: The source path in conflict.
        """
        super().__init__()
        self._target = target
        self._source = source

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Host-link collision: {self._target}")
            yield Label(f"Target and source both exist and differ:")
            yield Label(f"  target: {self._target}", classes="dim")
            yield Label(f"  source: {self._source}", classes="dim")
            yield Label("")
            yield Label("s = keep source (backup target)")
            yield Label("t = keep target (backup source)")
            yield Label("Esc = cancel pull")

    def action_keep_source(self) -> None:
        self.dismiss(Resolution.KEEP_SOURCE)

    def action_keep_target(self) -> None:
        self.dismiss(Resolution.KEEP_TARGET)

    def action_cancel(self) -> None:
        self.dismiss(Resolution.CANCEL)
```

**Export**: Add to `src/tools/dot/tui/widgets/__init__.py`:
```python
from dot.tui.widgets.rescue_modal import RescueCollisionModal

__all__ = [
    # ... existing ...
    "RescueCollisionModal",
]
```

---

### 2.5 TUI: action_pull Rewiring

**Module**: `src/tools/dot/tui/screens/main.py`

Replace the `action_pull` method:

```python
def action_pull(self) -> None:
    from dot.commands.pull.pull import CommandPull
    from dot.hostlinks.rescue import Resolution
    from dot.tui.widgets.rescue_modal import RescueCollisionModal

    cmd = CommandPull(
        self._git_ops.shell,
        self._dotfiles_root,
        git_service=self._git_ops,
    )
    plan = cmd.plan()

    if plan.error:
        self._show_message(plan.error)
        return

    resolutions: dict[str, Resolution] = {}

    def _process_collisions(collision_index: int = 0) -> None:
        if collision_index >= len(plan.collisions):
            # All collisions resolved, proceed to passphrase
            _do_pull()
            return

        entry = plan.collisions[collision_index]

        def _on_resolution(resolution: Resolution) -> None:
            if resolution == Resolution.CANCEL:
                self._show_message("Pull cancelled; nothing changed")
                return
            resolutions[entry.target] = resolution
            _process_collisions(collision_index + 1)

        self.app.push_screen(
            RescueCollisionModal(entry.target, entry.source),
            callback=_on_resolution,
        )

    def _do_pull() -> None:
        if self._git_ops.shell.is_command_available("git-secret"):

            def _on_passphrase(passphrase: str | None) -> None:
                result = cmd.execute(
                    plan=plan,
                    resolutions=resolutions,
                    passphrase=passphrase,
                )
                self._show_message(result.output or result.error or "Pull complete")
                self.refresh_status()

            self.app.push_screen(PassphraseModal(), callback=_on_passphrase)
        else:
            result = cmd.execute(plan=plan, resolutions=resolutions)
            self._show_message(result.output or result.error or "Pull complete")
            self.refresh_status()

    if plan.collisions:
        _process_collisions()
    else:
        _do_pull()
```

**Flow**:
1. Create `CommandPull` with the shared `git_service`.
2. Call `plan()` to fetch and compute rescue plan.
3. If `plan.error`: show message, stop.
4. For each collision: push `RescueCollisionModal`, collect resolution.
5. If any `CANCEL`: show `"Pull cancelled; nothing changed"`, stop.
6. After all collisions resolved: proceed to passphrase modal (if git-secret), then `execute()`.

---

## Test Plan

### Phase 0 Tests

| PRD Acceptance Bullet | Test File | Test Case |
|----------------------|-----------|-----------|
| `fetch()` returns err text / "" | `test_git_service.py` | `TestDotGitServiceFetch.test_success_returns_empty_string`, `test_failure_returns_error` |
| `has_upstream()` bool | `test_git_service.py` | `TestDotGitServiceHasUpstream.test_true_when_upstream_exists`, `test_false_when_no_upstream` |
| `show_upstream_file()` | `test_git_service.py` | `TestDotGitServiceShowUpstreamFile.test_returns_content`, `test_returns_none_on_error` |
| `upstream_deleted_paths()` | `test_git_service.py` | `TestDotGitServiceUpstreamDeletedPaths.test_parses_nul_separated`, `test_returns_empty_on_error` |
| `untrack()` | `test_git_service.py` | `TestDotGitServiceUntrack.test_success`, `test_failure` |
| `append_entry` creates missing file | `test_hostlinks_manifest.py` | `TestAppendEntry.test_creates_missing_file` |
| `append_entry` adds trailing newline | `test_hostlinks_manifest.py` | `TestAppendEntry.test_adds_newline_if_missing` |
| `append_entry` round-trips | `test_hostlinks_manifest.py` | `TestAppendEntry.test_roundtrip_through_parse_manifest` |
| `console.choose` | `test_console_adapter.py` | `TestConsoleAdapterChoose.test_choose_delegates_to_prompt_ask` |

### Phase 1 Tests

| PRD Acceptance Bullet | Test File | Test Case |
|----------------------|-----------|-----------|
| `plan_rescue` move classification | `test_hostlinks_rescue.py` | `test_classifies_move_when_source_missing` |
| `plan_rescue` duplicate classification | `test_hostlinks_rescue.py` | `test_classifies_duplicate_when_bytes_match` |
| `plan_rescue` dir collision | `test_hostlinks_rescue.py` | `test_classifies_collision_when_dir` |
| `plan_rescue` file collision | `test_hostlinks_rescue.py` | `test_classifies_collision_when_bytes_differ` |
| `apply_rescue` KEEP_SOURCE | `test_hostlinks_rescue.py` | `test_apply_keep_source_backs_up_target` |
| `apply_rescue` KEEP_TARGET | `test_hostlinks_rescue.py` | `test_apply_keep_target_backs_up_source` |
| `apply_rescue` CANCEL | `test_hostlinks_rescue.py` | `test_apply_cancel_changes_nothing` |
| `apply_rescue` missing resolution | `test_hostlinks_rescue.py` | `test_apply_missing_resolution_fails` |
| `apply_rescue` existing backup | `test_hostlinks_rescue.py` | `test_apply_existing_backup_fails` |
| `plan_rescue` no upstream | `test_hostlinks_rescue.py` | `test_no_upstream_sets_skipped` |
| `CommandLocalize` file | `test_localize.py` | `test_localizes_tracked_file` |
| `CommandLocalize` dir | `test_localize.py` | `test_localizes_tracked_directory` |
| `CommandLocalize` default source | `test_localize.py` | `test_default_source_is_dot_local` |
| `CommandLocalize` `--to` source | `test_localize.py` | `test_custom_source_with_to_option` |
| `CommandLocalize` refusal: missing target | `test_localize.py` | `test_refuses_missing_target` |
| `CommandLocalize` refusal: target is link | `test_localize.py` | `test_refuses_target_is_link` |
| `CommandLocalize` refusal: source exists | `test_localize.py` | `test_refuses_source_exists` |
| `CommandLocalize` refusal: in manifest | `test_localize.py` | `test_refuses_already_in_manifest` |
| `CommandLocalize` refusal: git-secret | `test_localize.py` | `test_refuses_git_secret_file` |
| `CommandLocalize` untrack failure | `test_localize.py` | `test_untrack_failure_changes_nothing` |
| `CommandLocalize` link failure rollback | `test_localize.py` | `test_link_failure_rolls_back` |
| `CommandLocalize` manifest failure rollback | `test_localize.py` | `test_manifest_failure_rolls_back` |
| `CommandLocalize` stage failure warning | `test_localize.py` | `test_stage_failure_returns_warning` |
| `CommandLocalize` real-git untrack | `test_localize.py` | `test_real_git_localize_untracks` |

### Phase 2 Tests

| PRD Acceptance Bullet | Test File | Test Case |
|----------------------|-----------|-----------|
| Existing tests gain fetch stubs | `test_pull.py` | All 6 existing tests + `fetch.return_value = ""`, `has_upstream.return_value = False` |
| Noninteractive collision fails | `test_pull.py` | `test_noninteractive_collision_fails` |
| Paths unchanged on collision failure | `test_pull.py` | `test_collision_failure_leaves_paths_unchanged` |
| Pull not called on collision failure | `test_pull.py` | `test_collision_failure_does_not_call_pull` |
| TUI cancel stops pull | `test_rescue_modal.py` | `test_cancel_dismisses_with_cancel_resolution` |
| TUI keybindings | `test_rescue_modal.py` | `test_s_keeps_source`, `test_t_keeps_target` |
| Two-host: A localizes, B rescues | `test_pull_two_hosts.py` | `test_two_host_localize_then_pull_rescues` |
| Two-host: collision fails | `test_pull_two_hosts.py` | `test_two_host_collision_fails_noninteractive` |

### Two-Host Test Harness Design

**File**: `tests/tools/dot/test_pull_two_hosts.py`

```python
@pytest.fixture
def two_host_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a bare origin with two cloned hosts."""
    # Create bare origin
    origin = tmp_path / "origin.git"
    origin.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=origin, check=True)

    # Create host A worktree
    host_a = tmp_path / "host_a"
    subprocess.run(["git", "clone", str(origin), str(host_a)], check=True)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Host A")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "a@test.local")
    # ... configure bare repo with .buvis directory ...

    # Create host B worktree
    host_b = tmp_path / "host_b"
    subprocess.run(["git", "clone", str(origin), str(host_b)], check=True)
    # ... configure bare repo with .buvis directory ...

    return origin, host_a, host_b
```

**Test Scenarios**:

1. **Happy path**: A localizes tracked file → pushes → B has local uncommitted bytes → B pulls → B's bytes at source, target is link.

2. **Collision**: B also has a different source file → noninteractive failure → B's HEAD unchanged.

---

## Risks and Edge Cases

### Risk 1: Raw `git pull` Bypasses Rescue

**Resolution**: Documented in README/dot.rst. Git has no pre-pull hook; users must use `dot pull`.

### Risk 2: PRD 00095 Also Changes `dot pull`

**Resolution**: Both add a fetch before `cfg pull`. 00095 lands second, keeps one `fetch()` call, runs both pre-merge steps (rescue, then divergence save). Implementer must coordinate.

### Risk 3: Window Between Fetch and Pull

**Resolution**: Accepted. `cfg pull` re-fetches, so commits pushed in that gap are merged unplanned. Git still refuses to delete a locally modified file, so bytes survive.

### Risk 4: Symlink on Windows

**Resolution**: The existing `_create_link` in linker.py handles Windows junctions for directories and symlinks for files (with Developer Mode fallback). No change needed.

### Risk 5: Directory Collisions

**Resolution**: All directory collisions go to `collisions` list; never auto-merged. Backup preserves entire directory tree.

### Risk 6: Atomic Write Parent Directory Missing

**Resolution**: `append_entry` creates parent directories with `mkdir(parents=True, exist_ok=True)` before calling `atomic_write_text`.

### Edge Case: Trailing Newline in Manifest

**Resolution**: `append_entry` checks `not existing.endswith("\n")` and inserts a newline before the entry if needed. Handles empty files (which have no trailing newline) correctly.

### Edge Case: Target Under a Directory Entry

**Resolution**: `plan_rescue` checks both `deleted == target` and `deleted.startswith(target + "/")` to handle files deleted under a directory target.

### Edge Case: Backup Path Collision

**Resolution**: `apply_rescue` pre-checks all backup paths before any mutation. If any exists, returns failure immediately.

### Ambiguity: `_validate_path` Not Exported

**Resolution**: Import privately from manifest.py: `from dot.hostlinks.manifest import _validate_path`. Consider exporting if reuse grows.

---

## Module Dependency Graph

```
Phase 0 (Foundation)
├── git/service.py: fetch, has_upstream, show_upstream_file, upstream_deleted_paths, untrack
├── hostlinks/manifest.py: append_entry
└── pybase/console.py: choose

Phase 1 (Core)
├── hostlinks/rescue.py: Resolution, RescuePlan, plan_rescue, apply_rescue
│   └── depends on: manifest (parse_manifest), git/service (has_upstream, show_upstream_file, upstream_deleted_paths)
└── commands/localize/localize.py: CommandLocalize
    └── depends on: manifest (append_entry, read_manifest), git/service (untrack, stage, list_secrets, ls_files), linker (_create_link)

Phase 2 (Integration)
├── commands/pull/pull.py: CommandPull.plan, CommandPull.execute
│   └── depends on: hostlinks/rescue (plan_rescue, apply_rescue), materialize (CommandMaterialize)
├── cli.py: localize command, pull with prompts
│   └── depends on: CommandPull, CommandLocalize, console.choose
├── tui/widgets/rescue_modal.py: RescueCollisionModal
│   └── depends on: Resolution
└── tui/screens/main.py: action_pull
    └── depends on: CommandPull, RescueCollisionModal, PassphraseModal
```

---

## Summary

This design provides a complete implementation blueprint for PRD 00090. Key aspects:

1. **Phase 0**: Five new `DotGitService` methods with exact command strings, `append_entry` with atomic write semantics, `console.choose` with rich.Prompt delegation.

2. **Phase 1**: `hostlinks/rescue.py` with `Resolution` StrEnum, `RescuePlan` dataclass, and `plan_rescue`/`apply_rescue` functions with detailed classification and no-byte-loss guarantees. `CommandLocalize` with full mutation sequence and reverse-order rollback.

3. **Phase 2**: `CommandPull` refactored with `plan()`/`execute()` split, CLI prompts for TTY, `RescueCollisionModal` for TUI, and wired `action_pull`. Includes test premise guard for existing tests.

4. **Test Plan**: Comprehensive mapping from PRD acceptance bullets to concrete test cases, including two-host real-git test harness.

An implementer with no other context can build from this document alone.
