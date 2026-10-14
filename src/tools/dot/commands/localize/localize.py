"""Convert a tracked file or directory to a host-specific link."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService
from dot.hostlinks.linker import _create_link
from dot.hostlinks.manifest import (
    MANIFEST_PATH,
    HostLink,
    _validate_path,
    append_entry,
    read_manifest,
)

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter

__all__ = ["CommandLocalize"]


class _LocalizeError(Exception):
    """Internal error for rollback control flow."""

    pass


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

    def _check_preconditions(self, target_path: Path, source_path: Path, tracked: set[str]) -> str | None:
        """Validate the localize request; return an error string or None if OK."""
        links, _errors = read_manifest(self._root)
        secrets = set(self._git_service.list_secrets())
        secret_hit = next((f for f in tracked if f in secrets), None)

        checks: list[tuple[bool, str]] = [
            (not target_path.exists(), f"{self._target} does not exist"),
            (target_path.is_symlink(), f"{self._target} is already a link"),
            (source_path.exists() or source_path.is_symlink(), f"{self._source} already exists"),
            (self._target == self._source, "target equals source"),
            (
                any(link.target == self._target for link in links),
                f"{self._target} already listed in host-links manifest",
            ),
            (secret_hit is not None, f"{secret_hit} is a git-secret file; localize refused"),
        ]
        for failed, message in checks:
            if failed:
                return message

        # 00088 manifest rules: relative, no "..", not absolute.
        problem = _validate_path(self._target) or _validate_path(self._source)
        if problem:
            return f"invalid path: {problem}"

        return None

    def execute(self) -> CommandResult:
        """Execute the localize command.

        Returns:
            CommandResult with info lines on success, error on failure.
        """
        target_path = self._root / self._target
        source_path = self._root / self._source

        tracked = self._git_service.ls_files(self._target)
        refusal = self._check_preconditions(target_path, source_path, tracked)
        if refusal is not None:
            return CommandResult(success=False, error=refusal)

        return self._mutate(target_path, source_path, was_tracked=bool(tracked))

    def _mutate(self, target_path: Path, source_path: Path, *, was_tracked: bool) -> CommandResult:
        """Run the ordered mutation sequence with reverse-order rollback."""
        info: list[str] = []
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
            append_entry(self._root, HostLink(target=self._target, source=self._source))

            # Step 5: Stage the manifest
            stage_result = self._git_service.stage(MANIFEST_PATH)
            if not stage_result.success:
                return CommandResult(
                    success=True,
                    info=info,
                    warnings=[f"stage failed: {stage_result.error}; run 'dot add {MANIFEST_PATH}'"],
                )
            info.append(f"staged {MANIFEST_PATH}")

            return CommandResult(success=True, info=info)

        except (_LocalizeError, OSError) as exc:
            self._rollback(
                target_path,
                source_path,
                did_untrack=did_untrack,
                did_move=did_move,
                did_link=did_link,
            )
            return CommandResult(success=False, error=str(exc))

    def _rollback(
        self,
        target_path: Path,
        source_path: Path,
        *,
        did_untrack: bool,
        did_move: bool,
        did_link: bool,
    ) -> None:
        """Undo a partial mutation in reverse order."""
        if did_link and target_path.is_symlink():
            target_path.unlink(missing_ok=True)
        if did_move and source_path.exists():
            try:
                shutil.move(str(source_path), str(target_path))
            except OSError:
                pass
        if did_untrack:
            self._git_service.unstage(self._target)
