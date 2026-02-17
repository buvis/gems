from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandStatus:
    def __init__(self: CommandStatus, shell: ShellAdapter) -> None:
        self.shell = shell

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandStatus) -> CommandResult:
        warnings: list[str] = []

        if self.shell.is_command_available("git-secret"):
            err, out = self.shell.exe("cfg secret hide -m", Path(os.environ["DOTFILES_ROOT"]))

            if err:
                return CommandResult(success=False, error=f"Error revealing secrets: {err}\n{out}")

        err, out = self.shell.exe("cfg status", Path(os.environ["DOTFILES_ROOT"]))

        if err:
            return CommandResult(success=False, error=f"Error executing command: {err}")

        if out:
            modified_files = get_git_modified_files(out, Path.cwd())
            if modified_files:
                for m in modified_files:
                    warnings.append(f"{m} was modified")
                return CommandResult(success=True, warnings=warnings)
            elif "nothing to commit" in out:
                return CommandResult(success=True, output="No modifications found")
            else:
                return CommandResult(success=False, error="Unexpected git output", metadata={"details": out})

        return CommandResult(success=True, output="No modifications found")


def get_git_modified_files(git_output: str, relative_to: Path) -> list[Path]:
    modified_files = []

    for line in git_output.split("\n"):
        clean_line = line.strip()
        if clean_line.startswith("modified:"):
            parts = clean_line.split("modified:")
            if len(parts) > 1:
                file_path = parts[1].strip()
                absolute_path = Path(relative_to).joinpath(file_path).resolve()
                modified_files.append(absolute_path)
    return modified_files
