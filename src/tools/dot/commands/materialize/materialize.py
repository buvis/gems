from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.git.service import DotGitService
from dot.hostlinks import install_hooks as write_hooks, reconcile_links

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandMaterialize:
    def __init__(
        self: CommandMaterialize,
        shell: ShellAdapter,
        dotfiles_root: str,
        *,
        install_hooks: bool = True,
        git_service: DotGitService | None = None,
    ) -> None:
        self._shell = shell
        self.dotfiles_root = dotfiles_root
        self._install_hooks = install_hooks
        self._git_service = git_service

    def execute(self: CommandMaterialize) -> CommandResult:
        changes, problems = reconcile_links(Path(self.dotfiles_root), apply=True)
        if self._install_hooks:
            service = self._git_service or DotGitService(self._shell, self.dotfiles_root)
            hooks_dir = service.hooks_path()
            if hooks_dir is not None:
                try:
                    changes = [*changes, *write_hooks(hooks_dir)]
                except OSError as exc:
                    problems = [*problems, f"hooks: {exc}"]
        return CommandResult(success=True, info=changes, warnings=problems)
