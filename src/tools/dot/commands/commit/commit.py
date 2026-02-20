from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandCommit:
    def __init__(self: CommandCommit, shell: ShellAdapter, message: str) -> None:
        self.shell = shell
        self.message = message

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandCommit) -> CommandResult:
        warnings: list[str] = []

        if self.shell.is_command_available("git-secret"):
            err, out = self.shell.exe("cfg secret hide -m", Path(os.environ["DOTFILES_ROOT"]))

            if err:
                return CommandResult(success=False, error=f"Error hiding secrets: {err}\n{out}")

        err, _ = self.shell.exe(
            f"cfg commit -m {shlex.quote(self.message)}",
            Path(os.environ["DOTFILES_ROOT"]),
        )

        if err:
            return CommandResult(success=False, error=f"Commit failed: {err}")

        return CommandResult(success=True, output="Changes committed", warnings=warnings)
