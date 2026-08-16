from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandDelete:
    def __init__(self: CommandDelete, shell: ShellAdapter, dotfiles_root: str, file_path: str) -> None:
        self.file_path = file_path
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandDelete) -> CommandResult:
        return self.dot_git_service.delete(self.file_path)
