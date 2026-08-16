from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandPull:
    def __init__(self: CommandPull, shell: ShellAdapter, dotfiles_root: str) -> None:
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandPull) -> CommandResult:
        return self.dot_git_service.pull(passphrase=None)
