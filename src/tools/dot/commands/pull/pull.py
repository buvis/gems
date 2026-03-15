from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.adapters import console
from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandPull:
    def __init__(self: CommandPull, shell: ShellAdapter) -> None:
        self.shell = shell

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandPull) -> CommandResult:
        cwd = Path(os.environ["DOTFILES_ROOT"])

        err, _ = self.shell.exe("cfg pull", cwd)
        if err:
            return CommandResult(success=False, error=f"Pull failed: {err}")

        err, _ = self.shell.exe("cfg submodule foreach git reset --hard", cwd)
        if err:
            return CommandResult(success=False, error=f"Submodule reset failed: {err}")

        err, _ = self.shell.exe("cfg submodule update --init", cwd)
        if err:
            return CommandResult(success=False, error=f"Submodule init failed: {err}")

        err, _ = self.shell.exe("cfg submodule update --remote --merge", cwd)
        if err:
            return CommandResult(success=False, error=f"Submodule update failed: {err}")

        if self.shell.is_command_available("git-secret"):
            console.info("Decrypting secrets (GPG passphrase required)")
            err, _ = self.shell.exe("cfg secret reveal -f", cwd)
            if err:
                return CommandResult(success=False, error=f"Secret reveal failed: {err}")

        return CommandResult(success=True, output="Dotfiles pulled successfully")
