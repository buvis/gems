from __future__ import annotations

import os
from pathlib import Path

from buvis.pybase.adapters import ShellAdapter, console


class CommandAdd:
    def __init__(self: CommandAdd, file_path: str | None = None) -> None:
        self.shell = ShellAdapter(suppress_logging=True)

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        console.info(f"Working in {os.environ['DOTFILES_ROOT']}")

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

        self.file_path: Path | None = None

        if file_path:
            if Path(file_path).is_file():
                self.file_path = Path(file_path)
                console.info(f"Checking {self.file_path} for changes")
            elif Path(Path(os.environ["DOTFILES_ROOT"]) / file_path).is_file():
                self.file_path = Path(Path(os.environ["DOTFILES_ROOT"]) / file_path)
                console.info(f"Checking {self.file_path} for changes")
            else:
                console.warning(
                    f"File {file_path} doesn't exist. Proceeding with cherry picking all.",
                )
        else:
            console.info("No file specified, proceeding with cherry picking all.")

    def execute(self: CommandAdd) -> None:
        command = "cfg add -p"
        if self.file_path:
            command = f"cfg add -p {self.file_path}"
            err, _ = self.shell.exe(
                f"cfg ls-files --error-unmatch {self.file_path}",
                os.environ["DOTFILES_ROOT"],
            )

            if "returned non-zero exit status 1" in err:
                console.info(f"File {self.file_path} not tracked yet, adding it.")
                command = f"cfg add {self.file_path}"

        self.shell.interact(
            command,
            "Stage this hunk [y,n,q,a,d,j,J,g,/,e,?]?",
            os.environ["DOTFILES_ROOT"],
        )
