from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandEncrypt:
    def __init__(self: CommandEncrypt, shell: ShellAdapter, file_path: str) -> None:
        self.shell = shell
        self.file_path = file_path

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandEncrypt) -> CommandResult:
        if not self.shell.is_command_available("git-secret"):
            return CommandResult(success=False, error="git-secret is not installed")

        cwd = Path(os.environ["DOTFILES_ROOT"])

        err, _ = self.shell.exe(f"cfg secret add {self.file_path}", cwd)
        if err:
            return CommandResult(success=False, error=f"Failed to register file: {err}")

        err, _ = self.shell.exe("cfg secret hide -m", cwd)
        if err:
            return CommandResult(success=False, error=f"Failed to encrypt: {err}")

        stage_paths = f"{self.file_path}.secret .gitsecret/ .gitignore"
        err, _ = self.shell.exe(f"cfg add {stage_paths}", cwd)
        if err:
            return CommandResult(success=False, error=f"Failed to stage: {err}")

        return CommandResult(success=True, output=f"{self.file_path} encrypted and staged")
