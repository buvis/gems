from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandUnstage:
    def __init__(self: CommandUnstage, shell: ShellAdapter, file_path: str | None = None) -> None:
        self.shell = shell
        self.file_path = file_path

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandUnstage) -> CommandResult:
        if self.file_path:
            cmd = f"cfg reset HEAD -- {shlex.quote(self.file_path)}"
            msg = f"{self.file_path} unstaged"
        else:
            cmd = "cfg reset HEAD"
            msg = "All files unstaged"

        err, _ = self.shell.exe(cmd, Path(os.environ["DOTFILES_ROOT"]))

        if err:
            return CommandResult(success=False, error=f"Unstage failed: {err}")

        return CommandResult(success=True, output=msg)
