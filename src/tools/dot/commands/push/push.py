from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandPush:
    def __init__(self: CommandPush, shell: ShellAdapter, dotfiles_root: str) -> None:
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandPush) -> CommandResult:
        return self.dot_git_service.push()
