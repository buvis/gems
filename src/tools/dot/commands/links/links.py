from __future__ import annotations

from pathlib import Path

from buvis.pybase.result import CommandResult

from dot.hostlinks import reconcile_links


class CommandLinkStatus:
    def __init__(self: CommandLinkStatus, dotfiles_root: str) -> None:
        self.dotfiles_root = dotfiles_root

    def execute(self: CommandLinkStatus) -> CommandResult:
        _changes, problems = reconcile_links(Path(self.dotfiles_root), apply=False)
        return CommandResult(success=True, warnings=problems)
