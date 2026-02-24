from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandRun:
    def __init__(self: CommandRun, shell: ShellAdapter, args: tuple[str, ...]) -> None:
        self.shell = shell
        self.args = args

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandRun) -> CommandResult:
        cmd = "cfg " + " ".join(self.args)
        err, out = self.shell.exe(cmd, Path(os.environ["DOTFILES_ROOT"]))

        if err:
            return CommandResult(success=False, error=err)

        return CommandResult(success=True, output=out or "Done")
