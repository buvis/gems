from __future__ import annotations

import logging
import os
from pathlib import Path

from buvis.pybase.adapters import ShellAdapter


class CommandAdd:
    def __init__(self: CommandAdd, file_path: str | None = None) -> None:
        self.shell = ShellAdapter(suppress_logging=True)

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        logging.info("Working in %s", os.environ["DOTFILES_ROOT"])

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

        if file_path:
            if Path(file_path).is_file():
                self.file_path = Path(file_path)
                logging.info("Checking %s for changes", self.file_path)
            elif Path(Path(os.environ["DOTFILES_ROOT"]) / file_path).is_file():
                self.file_path = Path(Path(os.environ["DOTFILES_ROOT"]) / file_path)
                logging.info("Checking %s for changes", self.file_path)
            else:
                self.file_path = None
                logging.warning(
                    "File %s doesn't exist. Proceeding with cherry picking all.",
                    file_path,
                )
        else:
            self.file_path = None
            logging.info("No file specified, proceeding with cherry picking all.")

    def execute(self: CommandAdd) -> None:
        command = "cfg add -p"
        if self.file_path:
            command = f"cfg add -p {self.file_path}"
            err, _ = self.shell.exe(
                f"cfg ls-files --error-unmatch {self.file_path}",
                os.environ["DOTFILES_ROOT"],
            )

            if "returned non-zero exit status 1" in err:
                logging.info("File %s not tracked yet, adding it.", self.file_path)
                command = f"cfg add {self.file_path}"

        self.shell.interact(
            command,
            "Stage this hunk [y,n,q,a,d,j,J,g,/,e,?]?",
            os.environ["DOTFILES_ROOT"],
        )
