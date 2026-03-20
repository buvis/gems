from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandAdd:
    def __init__(self: CommandAdd, shell: ShellAdapter, file_path: str | None = None) -> None:
        self.shell = shell
        self.warnings: list[str] = []

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

        self.file_path: Path | None = None

        if file_path:
            if Path(file_path).exists():
                self.file_path = Path(file_path)
            elif (Path(os.environ["DOTFILES_ROOT"]) / file_path).exists():
                self.file_path = Path(os.environ["DOTFILES_ROOT"]) / file_path
            else:
                self.warnings.append(
                    f"Path {file_path} doesn't exist. Proceeding with cherry picking all.",
                )

    def execute(self: CommandAdd) -> CommandResult:
        dotfiles_root = Path(os.environ["DOTFILES_ROOT"])
        command = "cfg add -p"

        if self.file_path:
            if self.file_path.is_dir():
                _, untracked = self.shell.exe(
                    f"cfg ls-files --others --exclude-standard {self.file_path}",
                    dotfiles_root,
                )
                if untracked.strip():
                    self.shell.exe(
                        f"cfg add --intent-to-add {self.file_path}",
                        dotfiles_root,
                    )
                command = f"cfg add -p {self.file_path}"
            else:
                err, _ = self.shell.exe(
                    f"cfg ls-files --error-unmatch {self.file_path}",
                    dotfiles_root,
                )
                if "returned non-zero exit status 1" in err:
                    command = f"cfg add {self.file_path}"
                else:
                    command = f"cfg add -p {self.file_path}"

        self.shell.interact(command, dotfiles_root)
        return CommandResult(success=True, warnings=self.warnings)
