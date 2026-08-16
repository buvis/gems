from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandRm:
    def __init__(self: CommandRm, shell: ShellAdapter, dotfiles_root: str, file_path: str) -> None:
        self.file_path = file_path
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandRm) -> CommandResult:
        return self.dot_git_service.rm(self.file_path)
