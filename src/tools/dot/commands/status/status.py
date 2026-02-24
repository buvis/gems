from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter

_STATUS_LABELS = {
    "M": "modified",
    "A": "new file",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "type changed",
}


class CommandStatus:
    def __init__(self: CommandStatus, shell: ShellAdapter) -> None:
        self.shell = shell

        if not os.environ.get("DOTFILES_ROOT"):
            path_dotfiles = Path.home()
            os.environ.setdefault("DOTFILES_ROOT", str(path_dotfiles.resolve()))

        self.shell.alias(
            "cfg",
            "git --git-dir=${DOTFILES_ROOT}/.buvis/ --work-tree=${DOTFILES_ROOT}",
        )

    def execute(self: CommandStatus) -> CommandResult:
        warnings: list[str] = []

        if self.shell.is_command_available("git-secret"):
            err, out = self.shell.exe("cfg secret hide -m", Path(os.environ["DOTFILES_ROOT"]))

            if err:
                return CommandResult(success=False, error=f"Error hiding secrets: {err}\n{out}")

        err, out = self.shell.exe("cfg status --porcelain", Path(os.environ["DOTFILES_ROOT"]))

        if err:
            return CommandResult(success=False, error=f"Error executing command: {err}")

        if out and out.strip():
            staged, unstaged = parse_porcelain_status(out)
            if staged or unstaged:
                info: list[str] = []
                for path, change_type in staged:
                    info.append(f"staged: {path} {change_type}")
                for path, change_type in unstaged:
                    warnings.append(f"unstaged: {path} {change_type}")
                return CommandResult(success=True, info=info, warnings=warnings)

        return CommandResult(success=True, output="No modifications found")


def parse_porcelain_status(
    git_output: str,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Parse ``git status --porcelain`` output into staged and unstaged lists.

    Returns:
        Tuple of (staged, unstaged) where each is a list of (filepath, change_label).
    """
    staged: list[tuple[str, str]] = []
    unstaged: list[tuple[str, str]] = []

    for line in git_output.split("\n"):
        if len(line) < 3:
            continue

        index_status = line[0]
        worktree_status = line[1]
        filepath = line[3:]

        # untracked
        if index_status == "?" and worktree_status == "?":
            unstaged.append((filepath, "untracked"))
            continue

        if index_status != " " and index_status in _STATUS_LABELS:
            staged.append((filepath, _STATUS_LABELS[index_status]))

        if worktree_status != " " and worktree_status in _STATUS_LABELS:
            unstaged.append((filepath, _STATUS_LABELS[worktree_status]))

    return staged, unstaged
