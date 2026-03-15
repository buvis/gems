from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandPush:
    def __init__(self: CommandPush, shell: ShellAdapter) -> None:
        self.shell = shell

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandPush) -> CommandResult:
        dotfiles_root = Path(os.environ["DOTFILES_ROOT"])

        if not self._has_unpushed_commits(dotfiles_root):
            return CommandResult(success=True, output="Nothing to push")

        err, _ = self.shell.exe("cfg push", dotfiles_root)

        if err:
            return CommandResult(success=False, error=f"Push failed: {err}")

        return CommandResult(success=True, output="Changes pushed")

    def _has_unpushed_commits(self: CommandPush, dotfiles_root: Path) -> bool:
        err, out = self.shell.exe(
            "cfg rev-list --count @{u}..HEAD",
            dotfiles_root,
        )

        if err or not out or not out.strip():
            return False

        try:
            return int(out.strip()) > 0
        except ValueError:
            return False
