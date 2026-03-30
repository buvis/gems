from __future__ import annotations

import os
import shlex
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.tui.models import BranchInfo, FileEntry

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter

__all__ = ["GitOps"]


class GitOps:
    """Wrap bare-repo git commands for the dotfiles TUI."""

    def __init__(self, shell: ShellAdapter, dotfiles_root: str) -> None:
        self.shell = shell
        self.dotfiles_root = dotfiles_root
        self._wd = Path(dotfiles_root)
        os.environ.setdefault("DOTFILES_ROOT", dotfiles_root)
        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def status(self) -> list[FileEntry]:
        has_secret = self.shell.is_command_available("git-secret")
        err, out = self.shell.exe("cfg status --porcelain", self._wd)

        if err or not out or not out.strip():
            return []

        secrets: set[str] = set()
        if has_secret:
            serr, sout = self.shell.exe("cfg secret list", self._wd)
            if not serr and sout:
                secrets = {
                    line for line in sout.strip().split("\n") if line
                }

        entries: list[FileEntry] = []
        for line in out.split("\n"):
            if len(line) < 3:
                continue
            status_code = line[:2]
            filepath = line[3:]
            entries.append(
                FileEntry(
                    path=filepath,
                    status=status_code,
                    is_secret=filepath in secrets,
                )
            )

        return entries

    def diff(self, path: str, staged: bool = False) -> str:
        cached = " --cached" if staged else ""
        _err, out = self.shell.exe(
            f"cfg diff{cached} {shlex.quote(path)}", self._wd
        )
        return out

    def stage(self, path: str) -> CommandResult:
        err, _out = self.shell.exe(
            f"cfg add {shlex.quote(path)}", self._wd
        )
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def unstage(self, path: str) -> CommandResult:
        err, _out = self.shell.exe(
            f"cfg reset HEAD -- {shlex.quote(path)}", self._wd
        )
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def commit(self, message: str) -> CommandResult:
        if self.shell.is_command_available("git-secret"):
            err, _out = self.shell.exe("cfg secret hide -m", self._wd)
            if err:
                return CommandResult(success=False, error=err)

        err, _out = self.shell.exe(
            f"cfg commit -m {shlex.quote(message)}", self._wd
        )
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def push(self) -> CommandResult:
        if not self._has_unpushed_commits():
            return CommandResult(success=True, output="Nothing to push")

        err, _out = self.shell.exe("cfg push", self._wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True, output="Changes pushed")

    def pull(self) -> CommandResult:
        err, _out = self.shell.exe("cfg pull", self._wd)
        if err:
            return CommandResult(success=False, error=err)

        err, _out = self.shell.exe("cfg submodule foreach git reset --hard", self._wd)
        if err:
            return CommandResult(success=False, error=f"Submodule reset failed: {err}")

        err, _out = self.shell.exe("cfg submodule update --init", self._wd)
        if err:
            return CommandResult(success=False, error=f"Submodule init failed: {err}")

        err, _out = self.shell.exe("cfg submodule update --remote --merge", self._wd)
        if err:
            return CommandResult(success=False, error=f"Submodule update failed: {err}")

        if self.shell.is_command_available("git-secret"):
            err, _out = self.shell.exe("cfg secret reveal -f", self._wd)
            if err:
                return CommandResult(success=False, error=f"Secret reveal failed: {err}")

        return CommandResult(success=True, output="Dotfiles pulled successfully")

    def has_uncommitted_changes(self) -> bool:
        err, out = self.shell.exe("cfg status --porcelain", self._wd)
        if err:
            return False
        return bool(out and out.strip())

    def has_unpushed_commits(self) -> bool:
        return self._has_unpushed_commits()

    def _has_unpushed_commits(self) -> bool:
        err, out = self.shell.exe("cfg rev-list --count @{u}..HEAD", self._wd)
        if err:
            return True
        if not out or not out.strip():
            return False
        try:
            return int(out.strip()) > 0
        except ValueError:
            return False

    def add_to_gitignore(self, pattern: str) -> CommandResult:
        try:
            gitignore = self._wd / ".gitignore"
            with gitignore.open("a") as f:
                f.write(f"{pattern}\n")
        except OSError as exc:
            return CommandResult(success=False, error=str(exc))
        return self.stage(".gitignore")

    def rm(self, path: str) -> CommandResult:
        err, _out = self.shell.exe(
            f"cfg rm {shlex.quote(path)}", self._wd
        )
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def apply_patch(self, patch: str) -> CommandResult:
        """Stage changes from a patch string using git apply --cached."""
        fd, tmpfile = tempfile.mkstemp(suffix=".patch")
        try:
            os.write(fd, patch.encode())
            os.close(fd)
            err, _out = self.shell.exe(
                f"cfg apply --cached {tmpfile}", self._wd
            )
            if err:
                return CommandResult(success=False, error=err)
            return CommandResult(success=True)
        finally:
            if Path(tmpfile).exists():
                os.unlink(tmpfile)

    def apply_patch_reverse(self, patch: str) -> CommandResult:
        """Unstage changes by applying a patch in reverse."""
        fd, tmpfile = tempfile.mkstemp(suffix=".patch")
        try:
            os.write(fd, patch.encode())
            os.close(fd)
            err, _out = self.shell.exe(
                f"cfg apply --cached --reverse {tmpfile}", self._wd
            )
            if err:
                return CommandResult(success=False, error=err)
            return CommandResult(success=True)
        finally:
            if Path(tmpfile).exists():
                os.unlink(tmpfile)

    def branch_info(self) -> BranchInfo:
        name = "unknown"
        ahead = 0
        behind = 0
        secret_count = 0

        err, out = self.shell.exe(
            "cfg rev-parse --abbrev-ref HEAD", self._wd
        )
        if not err and out and out.strip():
            name = out.strip()

        err, out = self.shell.exe(
            "cfg rev-list --count --left-right @{u}...HEAD", self._wd
        )
        if not err and out and out.strip():
            parts = out.strip().split("\t")
            if len(parts) == 2:
                try:
                    behind = int(parts[0])
                    ahead = int(parts[1])
                except ValueError:
                    pass

        if self.shell.is_command_available("git-secret"):
            err, out = self.shell.exe("cfg secret list", self._wd)
            if not err and out and out.strip():
                secret_count = len(
                    [line for line in out.strip().split("\n") if line]
                )

        return BranchInfo(
            name=name,
            ahead=ahead,
            behind=behind,
            secret_count=secret_count,
        )
