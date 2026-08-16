from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandUnstage:
    def __init__(
        self: CommandUnstage,
        shell: ShellAdapter,
        dotfiles_root: str,
        file_path: str | None = None,
    ) -> None:
        self.shell = shell
        self.file_path = file_path
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandUnstage) -> CommandResult:
        return self.dot_git_service.unstage(self.file_path)
