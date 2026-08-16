from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService

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
    def __init__(self: CommandStatus, shell: ShellAdapter, dotfiles_root: str) -> None:
        self.dot_git_service = DotGitService(shell, dotfiles_root)

    def execute(self: CommandStatus) -> CommandResult:
        warnings: list[str] = []
        info: list[str] = []

        entries, hide_error = self.dot_git_service.status()
        if hide_error:
            return CommandResult(success=False, error=f"Error hiding secrets: {hide_error}")

        for entry in entries:
            index_status, worktree_status = entry.status[0], entry.status[1]
            if index_status == "?" and worktree_status == "?":
                warnings.append(f"unstaged: {entry.path} untracked")
                continue
            if index_status != " " and index_status in _STATUS_LABELS:
                info.append(f"staged: {entry.path} {_STATUS_LABELS[index_status]}")
            if worktree_status != " " and worktree_status in _STATUS_LABELS:
                warnings.append(f"unstaged: {entry.path} {_STATUS_LABELS[worktree_status]}")

        branch = self.dot_git_service.branch_info()
        if branch.ahead:
            warnings.append(f"{branch.ahead} commit(s) not pushed")
        if branch.behind:
            warnings.append(f"{branch.behind} commit(s) not pulled")

        if not info and not warnings:
            return CommandResult(success=True, output="No modifications found")

        return CommandResult(success=True, info=info, warnings=warnings)
