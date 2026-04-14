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
        self.wd = Path(dotfiles_root)
        os.environ.setdefault("DOTFILES_ROOT", dotfiles_root)
        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )
        self._ensure_fetch_refspec()

    def _ensure_fetch_refspec(self) -> None:
        """Add fetch refspec if missing (common in bare-repo dotfiles setups)."""
        err, out = self.shell.exe("cfg config remote.origin.fetch", self.wd)
        if err or not out or not out.strip():
            self.shell.exe(
                "cfg config remote.origin.fetch +refs/heads/*:refs/remotes/origin/*",
                self.wd,
            )

    def status(self) -> list[FileEntry]:
        has_secret = self.shell.is_command_available("git-secret")
        err, out = self.shell.exe("cfg status --porcelain", self.wd)

        if err or not out or not out.strip():
            return []

        secrets: set[str] = set()
        if has_secret:
            serr, sout = self.shell.exe("cfg secret list", self.wd)
            if not serr and sout:
                secrets = {line for line in sout.strip().split("\n") if line}

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
        _err, out = self.shell.exe(f"cfg diff{cached} {shlex.quote(path)}", self.wd)
        return out

    def stage(self, path: str) -> CommandResult:
        err, _out = self.shell.exe(f"cfg add {shlex.quote(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def unstage(self, path: str) -> CommandResult:
        err, _out = self.shell.exe(f"cfg reset HEAD -- {shlex.quote(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def commit(self, message: str) -> CommandResult:
        if self.shell.is_command_available("git-secret"):
            err, _out = self.shell.exe("cfg secret hide -m", self.wd)
            if err:
                return CommandResult(success=False, error=err)

        err, _out = self.shell.exe(f"cfg commit -m {shlex.quote(message)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def push(self) -> CommandResult:
        if not self._has_unpushed_commits():
            return CommandResult(success=True, output="Nothing to push")

        err, _out = self.shell.exe("cfg push", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True, output="Changes pushed")

    def pull(self, passphrase: str | None = None) -> CommandResult:
        err, _out = self.shell.exe("cfg pull", self.wd)
        if err:
            return CommandResult(success=False, error=err)

        err, _out = self.shell.exe("cfg submodule foreach git reset --hard", self.wd)
        if err:
            return CommandResult(success=False, error=f"Submodule reset failed: {err}")

        err, _out = self.shell.exe("cfg submodule update --init", self.wd)
        if err:
            return CommandResult(success=False, error=f"Submodule init failed: {err}")

        err, _out = self.shell.exe("cfg submodule update --remote --merge", self.wd)
        if err:
            return CommandResult(success=False, error=f"Submodule update failed: {err}")

        if self.shell.is_command_available("git-secret"):
            cmd = "cfg secret reveal -f"
            if passphrase:
                cmd += f" -p {shlex.quote(passphrase)}"
            err, _out = self.shell.exe(cmd, self.wd)
            if err:
                return CommandResult(success=False, error=f"Secret reveal failed: {err}")

        return CommandResult(success=True, output="Dotfiles pulled successfully")

    def has_uncommitted_changes(self) -> bool:
        err, out = self.shell.exe("cfg status --porcelain", self.wd)
        if err:
            return False
        return bool(out and out.strip())

    def has_unpushed_commits(self) -> bool:
        return self._has_unpushed_commits()

    def _has_unpushed_commits(self) -> bool:
        err, out = self.shell.exe("cfg rev-list --count @{u}..HEAD", self.wd)
        if err:
            berr, bout = self.shell.exe("cfg rev-parse --abbrev-ref HEAD", self.wd)
            if berr or not bout or not bout.strip():
                return False
            branch = bout.strip()
            err, out = self.shell.exe(f"cfg rev-list --count origin/{branch}..HEAD", self.wd)
        if err or not out or not out.strip():
            return False
        try:
            return int(out.strip()) > 0
        except ValueError:
            return False

    def add_to_gitignore(self, pattern: str) -> CommandResult:
        try:
            gitignore = self.wd / ".gitignore"
            with gitignore.open("a") as f:
                f.write(f"{pattern}\n")
        except OSError as exc:
            return CommandResult(success=False, error=str(exc))
        return self.stage(".gitignore")

    def rm(self, path: str) -> CommandResult:
        err, _out = self.shell.exe(f"cfg rm {shlex.quote(path)}", self.wd)
        if err:
            return CommandResult(success=False, error=err)
        return CommandResult(success=True)

    def _run_patch(self, patch: str, flags: str) -> CommandResult:
        fd, tmpfile = tempfile.mkstemp(suffix=".patch")
        try:
            os.write(fd, patch.encode())
            os.close(fd)
            err, _out = self.shell.exe(f"cfg apply {flags} {tmpfile}", self.wd)
            if err:
                return CommandResult(success=False, error=err)
            return CommandResult(success=True)
        finally:
            if Path(tmpfile).exists():
                os.unlink(tmpfile)

    def apply_patch(self, patch: str) -> CommandResult:
        """Stage changes from a patch string using git apply --cached."""
        return self._run_patch(patch, "--cached")

    def apply_reverse_to_worktree(self, patch: str) -> CommandResult:
        """Revert working-tree changes (no ``--cached``, unlike ``apply_patch_reverse``)."""
        return self._run_patch(patch, "--reverse")

    def apply_patch_reverse(self, patch: str) -> CommandResult:
        """Unstage changes by applying a patch in reverse."""
        return self._run_patch(patch, "--cached --reverse")

    def branch_info(self) -> BranchInfo:
        name = "unknown"
        ahead = 0
        behind = 0
        secret_count = 0

        err, out = self.shell.exe("cfg rev-parse --abbrev-ref HEAD", self.wd)
        if not err and out and out.strip():
            name = out.strip()

        err, out = self.shell.exe("cfg rev-list --count --left-right @{u}...HEAD", self.wd)
        if err:
            err, out = self.shell.exe(
                f"cfg rev-list --count --left-right origin/{name}...HEAD",
                self.wd,
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
            err, out = self.shell.exe("cfg secret list", self.wd)
            if not err and out and out.strip():
                secret_count = len([line for line in out.strip().split("\n") if line])

        return BranchInfo(
            name=name,
            ahead=ahead,
            behind=behind,
            secret_count=secret_count,
        )
