from __future__ import annotations

import os
from pathlib import Path

from buvis.pybase.adapters import ShellAdapter, console


class CommandStatus:
    def __init__(self: CommandStatus) -> None:
        self.shell = ShellAdapter(suppress_logging=True)

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        console.info(f"Working in {os.environ['DOTFILES_ROOT']}")

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandStatus) -> None:
        err = ""
        out = ""

        if self.shell.is_command_available("git-secret"):
            err, out = self.shell.exe("cfg secret hide -m", os.environ["DOTFILES_ROOT"])

            if err:
                console.failure("Error revealing secrets", details=f"{err}\n{out}")
                return

        err, out = self.shell.exe("cfg status", os.environ["DOTFILES_ROOT"])

        if err:
            console.failure(f"Error executing command: {err}")

        if out:
            modified_files = get_git_modified_files(out, Path.cwd())
            if modified_files:
                for m in modified_files:
                    console.warning(f"{m} was modified")
            elif "nothing to commit" in out:
                console.success("No modifications found")
            else:
                console.failure("Unexpected git output", details=out)


def get_git_modified_files(git_output: str, relative_to: Path) -> list[Path]:
    modified_files = []

    for line in git_output.split("\n"):
        clean_line = line.strip()
        if clean_line.startswith("modified:"):
            parts = clean_line.split("modified:")
            if len(parts) > 1:
                file_path = parts[1].strip()
                absolute_path = Path(relative_to).joinpath(file_path).resolve()
                modified_files.append(absolute_path)
    return modified_files
