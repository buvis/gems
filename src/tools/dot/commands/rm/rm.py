from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandRm:
    def __init__(self: CommandRm, shell: ShellAdapter, file_path: str) -> None:
        self.shell = shell
        self.file_path = file_path
        self.warnings: list[str] = []

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def _is_encrypted(self: CommandRm) -> bool:
        cwd = Path(os.environ["DOTFILES_ROOT"])
        err, out = self.shell.exe("cfg secret list", cwd)
        if err:
            self.warnings.append(f"Could not check git-secret status: {err}")
            return False
        return self.file_path in out.splitlines()

    def _remove_normal(self: CommandRm) -> CommandResult:
        cwd = Path(os.environ["DOTFILES_ROOT"])
        err, _ = self.shell.exe(f"cfg rm {self.file_path}", cwd)
        if err:
            return CommandResult(success=False, error=f"Failed to remove: {err}")
        return CommandResult(success=True, output=f"{self.file_path} removed from dotfiles", warnings=self.warnings)

    def _remove_encrypted(self: CommandRm) -> CommandResult:
        cwd = Path(os.environ["DOTFILES_ROOT"])

        err, _ = self.shell.exe(f"cfg secret remove -c {self.file_path}", cwd)
        if err:
            return CommandResult(success=False, error=f"Failed to remove from git-secret: {err}")

        gitignore = cwd / ".gitignore"
        if gitignore.exists():
            lines = gitignore.read_text().splitlines()
            lines = [line for line in lines if line != self.file_path]
            gitignore.write_text(("\n".join(lines) + "\n") if lines else "")

        err, _ = self.shell.exe("cfg add .gitignore", cwd)
        if err:
            self.warnings.append(f"Failed to stage .gitignore: {err}")

        plaintext = cwd / self.file_path
        if plaintext.exists():
            try:
                plaintext.unlink()
            except OSError as exc:
                return CommandResult(success=False, error=f"Failed to delete plaintext: {exc}")

        return CommandResult(
            success=True, output=f"{self.file_path} removed from git-secret and disk", warnings=self.warnings,
        )

    def execute(self: CommandRm) -> CommandResult:
        if self._is_encrypted():
            return self._remove_encrypted()
        return self._remove_normal()
