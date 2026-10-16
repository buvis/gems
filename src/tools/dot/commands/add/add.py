from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandAdd:
    def __init__(
        self: CommandAdd,
        shell: ShellAdapter,
        dotfiles_root: str,
        file_path: str | None = None,
    ) -> None:
        self.dot_git_service = DotGitService(shell, dotfiles_root)
        self.file_path: Path | None = None
        self.missing_path: str | None = None

        if file_path:
            if os.path.lexists(file_path):
                self.file_path = Path(os.path.abspath(file_path))
            elif os.path.lexists(os.path.join(dotfiles_root, file_path)):
                self.file_path = Path(dotfiles_root) / file_path
            else:
                self.missing_path = file_path

    def execute(self: CommandAdd) -> CommandResult:
        if self.missing_path:
            return CommandResult(success=False, error=f"Path {self.missing_path} doesn't exist")
        return self.dot_git_service.stage_interactive(str(self.file_path) if self.file_path else None)
