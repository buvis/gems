from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.commands.materialize.materialize import CommandMaterialize
from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter

_CHECKOUT_CONFLICT = (
    "checkout conflicts with existing files, nothing overwritten:\n{err}\nmove them away, then run: dot run checkout"
)


class CommandSetup:
    def __init__(self: CommandSetup, shell: ShellAdapter, dotfiles_root: str, remote_url: str) -> None:
        self._shell = shell
        self.dotfiles_root = dotfiles_root
        self.remote_url = remote_url

    def execute(self: CommandSetup) -> CommandResult:
        buvis_dir = f"{self.dotfiles_root}/.buvis"
        if Path(buvis_dir).exists():
            return CommandResult(success=False, error=f"already set up: {buvis_dir} exists")
        err, _out = self._shell.exe(
            f"git clone --bare -- {shlex.quote(self.remote_url)} {shlex.quote(buvis_dir)}",
            Path(self.dotfiles_root),
        )
        if err:
            return CommandResult(success=False, error=f"clone failed: {err}")
        info = [f"cloned {self.remote_url}"]
        warnings: list[str] = []
        service = DotGitService(self._shell, self.dotfiles_root)  # alias, refspec, hooksPath
        err, _out = self._shell.exe("cfg config status.showUntrackedFiles no", service.wd)
        if err:
            warnings.append(f"status.showUntrackedFiles not set: {err}")
        err = self._set_upstream(service)
        if err:
            warnings.append(f"upstream not set: {err}")
        # Plain checkout silently overwrites ignored untracked files.
        err, _out = self._shell.exe("cfg checkout --no-overwrite-ignore", service.wd)
        if err:
            return CommandResult(
                success=False,
                error=_CHECKOUT_CONFLICT.format(err=err),
                info=info,
                warnings=warnings,
            )
        info.append("checked out")
        materialized = CommandMaterialize(
            self._shell, self.dotfiles_root, install_hooks=True, git_service=service
        ).execute()
        return CommandResult(
            success=True,
            info=[*info, *materialized.info],
            warnings=[*warnings, *materialized.warnings],
        )

    def _set_upstream(self: CommandSetup, service: DotGitService) -> str:
        err, _out = self._shell.exe("cfg fetch origin", service.wd)
        if err:
            return err
        err, out = self._shell.exe("cfg rev-parse --abbrev-ref HEAD", service.wd)
        if err:
            return err
        err, _out = self._shell.exe(f"cfg branch {shlex.quote('--set-upstream-to=origin/' + out.strip())}", service.wd)
        return err
