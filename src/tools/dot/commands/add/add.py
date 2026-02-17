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
            if Path(file_path).is_file():
                self.file_path = Path(file_path)
            elif Path(Path(Path(os.environ["DOTFILES_ROOT"])) / file_path).is_file():
                self.file_path = Path(Path(Path(os.environ["DOTFILES_ROOT"])) / file_path)
            else:
                self.warnings.append(
                    f"File {file_path} doesn't exist. Proceeding with cherry picking all.",
                )

    def execute(self: CommandAdd) -> CommandResult:
        command = "cfg add -p"
        if self.file_path:
            command = f"cfg add -p {self.file_path}"
            err, _ = self.shell.exe(
                f"cfg ls-files --error-unmatch {self.file_path}",
                Path(os.environ["DOTFILES_ROOT"]),
            )

            if "returned non-zero exit status 1" in err:
                command = f"cfg add {self.file_path}"

        self.shell.interact(
            command,
            "Stage this hunk [y,n,q,a,d,j,J,g,/,e,?]?",
            Path(os.environ["DOTFILES_ROOT"]),
        )
        return CommandResult(success=True, warnings=self.warnings)
