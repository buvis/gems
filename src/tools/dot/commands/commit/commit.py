from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandCommit:
    def __init__(self: CommandCommit, shell: ShellAdapter, dotfiles_root: str, message: str) -> None:
        self.message = message
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandCommit) -> CommandResult:
        return self.dot_git_service.commit(self.message)
