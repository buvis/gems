"""``klyreon maintain [--dry-run]`` -- the autonomous maintenance sweep.

Refuses in a non-git vault through PRD A's autonomy gate; holds the
single-instance lock for the run (an invocation that cannot take it exits 0
with an info line, since overlapping cron ticks are expected); runs the sweep;
exit 1 when lint found errors (the transitions still applied). Makes no LLM
call. ``--dry-run`` reports every transition and candidate and writes nothing.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from buvis.pybase.result import CommandResult

from klyreon.maintain.sweep import MaintainResult, run_maintain
from klyreon.run.lock import LockBusyError, vault_lock
from klyreon.vault.git import GitIdentity, require_git_for_autonomy

__all__ = ["CommandMaintain"]


class CommandMaintain:
    """Run one maintenance sweep over the vault, or report it under dry-run."""

    def __init__(  # noqa: PLR0913 - CLI-mirroring knobs, each with a configured default
        self,
        root: Path,
        *,
        max_body_lines: int = 60,
        prune_window_days: int = 365,
        pruning_enabled: bool = False,
        dry_run: bool = False,
        identity: GitIdentity | None = None,
        now: dt.datetime | None = None,
    ) -> None:
        self.root = root
        self.max_body_lines = max_body_lines
        self.prune_window_days = prune_window_days
        self.pruning_enabled = pruning_enabled
        self.dry_run = dry_run
        self.identity = identity or GitIdentity(name="klyreon", email="klyreon@localhost")
        self.now = now

    def execute(self) -> CommandResult:
        gate = require_git_for_autonomy(self.root)
        if not gate.success:
            return CommandResult(success=False, error=gate.error)

        now = self.now or dt.datetime.now().astimezone()
        try:
            with vault_lock(self.root):
                result = run_maintain(
                    self.root,
                    identity=self.identity,
                    now=now,
                    max_body_lines=self.max_body_lines,
                    prune_window_days=self.prune_window_days,
                    pruning_enabled=self.pruning_enabled,
                    dry_run=self.dry_run,
                )
        except LockBusyError as exc:
            return CommandResult(success=True, output=str(exc), info=["another run holds the lock; exiting cleanly"])

        return self._to_result(result)

    def _to_result(self, result: MaintainResult) -> CommandResult:
        prefix = "dry-run: " if result.dry_run else ""
        transition_lines = [f"{t.path}: {t.field} {t.old} -> {t.new}" for t in result.transitions]
        candidate_lines = [f"{c.path}: {c.reason}" for c in result.prune_candidates]
        deletion_note = "enabled" if self.pruning_enabled else "report-only (set pruning_enabled to delete)"
        lines = [
            f"{prefix}lint findings: {result.lint_errors}",
            f"{prefix}transitions: {len(result.transitions)}",
            *[f"  {ln}" for ln in transition_lines],
            f"{prefix}MOCs reconciled: {len(result.moc_reconciled)}",
            f"{prefix}prune candidates: {len(result.prune_candidates)} (deletion {deletion_note})",
            *[f"  {ln}" for ln in candidate_lines],
            f"{prefix}pruned: {len(result.pruned)}",
        ]
        if result.trail:
            lines.append(f"trail: {result.trail}")

        output = "\n".join(lines)
        # Lint errors fail the command (exit 1) but the transitions still landed.
        success = result.lint_errors == 0
        return CommandResult(
            success=success,
            output=output if success else None,
            error=output if not success else None,
            metadata={
                "dry_run": result.dry_run,
                "lint_errors": result.lint_errors,
                "transitions": len(result.transitions),
                "moc_reconciled": len(result.moc_reconciled),
                "prune_candidates": len(result.prune_candidates),
                "pruned": len(result.pruned),
                "trail": result.trail,
            },
        )
