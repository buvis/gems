from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from buvis.pybase.result import CommandResult

from dot.commands.materialize.materialize import CommandMaterialize
from dot.git.service import DotGitService
from dot.hostlinks.rescue import RescuePlan, Resolution, apply_rescue, plan_rescue

if TYPE_CHECKING:
    from buvis.pybase.adapters.shell.shell import ShellAdapter


class CommandPull:
    """Pull dotfiles with host-link rescue."""

    def __init__(
        self,
        shell: ShellAdapter,
        dotfiles_root: str,
        *,
        git_service: DotGitService | None = None,
    ) -> None:
        """Initialize the pull command.

        Args:
            shell: Shell adapter for git commands.
            dotfiles_root: Path to the dotfiles root directory.
            git_service: Optional pre-initialized git service.
        """
        self._shell = shell
        self._dotfiles_root = dotfiles_root
        self._root = Path(dotfiles_root)
        self.dot_git_service = git_service or DotGitService(shell, dotfiles_root)

    def plan(self) -> RescuePlan:
        """Fetch and plan the rescue.

        Returns:
            RescuePlan describing what needs to happen.
        """
        fetch_err = self.dot_git_service.fetch()
        if fetch_err:
            return RescuePlan(error=f"Fetch failed: {fetch_err}")

        return plan_rescue(self._root, self.dot_git_service)

    def execute(
        self,
        plan: RescuePlan | None = None,
        resolutions: dict[str, Resolution] | None = None,
        passphrase: str | None = None,
    ) -> CommandResult:
        """Execute the pull with rescue.

        Args:
            plan: Pre-computed rescue plan; computed fresh if None.
            resolutions: Collision resolutions keyed by target.
            passphrase: GPG passphrase for secret reveal.

        Returns:
            CommandResult with combined info/warnings from rescue, pull, and materialize.
        """
        if plan is None:
            plan = self.plan()

        if plan.error:
            return CommandResult(success=False, error=plan.error)

        # Apply rescue
        rescue_result = apply_rescue(self._root, plan, resolutions)
        if not rescue_result.success:
            return rescue_result

        rescued_sources = [e.source for e in plan.moves + plan.duplicates + plan.collisions]

        # Execute pull
        pull_result = self.dot_git_service.pull(passphrase=passphrase)
        if not pull_result.success:
            error = pull_result.error or "Pull failed"
            if rescued_sources:
                error += f"; rescued files are at: {', '.join(rescued_sources)}"
            return CommandResult(success=False, error=error)

        # Materialize links
        mat_result = CommandMaterialize(
            self._shell,
            self._dotfiles_root,
            install_hooks=False,
            git_service=self.dot_git_service,
        ).execute()

        # Merge results
        info = list(rescue_result.info) + list(mat_result.info)
        warnings = list(rescue_result.warnings) + list(mat_result.warnings)
        if plan.skipped:
            warnings.append(plan.skipped)

        return CommandResult(
            success=True,
            output=pull_result.output,
            info=info,
            warnings=warnings,
        )
