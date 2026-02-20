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
        err, _ = self.shell.exe("cfg push", Path(os.environ["DOTFILES_ROOT"]))

        if err:
            return CommandResult(success=False, error=f"Push failed: {err}")

        return CommandResult(success=True, output="Changes pushed")
