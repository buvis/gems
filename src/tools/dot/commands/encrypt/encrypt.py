from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandEncrypt:
    def __init__(self: CommandEncrypt, shell: ShellAdapter, dotfiles_root: str, file_path: str) -> None:
        self.file_path = file_path
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandEncrypt) -> CommandResult:
        if not self.dot_git_service.is_secret_tool_available():
            return CommandResult(success=False, error="git-secret is not installed")
        return self.dot_git_service.encrypt_and_stage(self.file_path)
