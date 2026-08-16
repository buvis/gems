from __future__ import annotations

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
        self.warnings: list[str] = []
        self.file_path: Path | None = None

        if file_path:
            if Path(file_path).exists():
                self.file_path = Path(file_path)
            elif (Path(dotfiles_root) / file_path).exists():
                self.file_path = Path(dotfiles_root) / file_path
            else:
                self.warnings.append(
                    f"Path {file_path} doesn't exist. Proceeding with cherry picking all.",
                )

    def execute(self: CommandAdd) -> CommandResult:
        self.dot_git_service.stage_interactive(str(self.file_path) if self.file_path else None)
        return CommandResult(success=True, warnings=self.warnings)
