"""``klyreon ingest [PATH]`` -- source documents to committed zettels.

Refuses in a non-git vault through PRD A's autonomy gate; holds the
single-instance lock for the run (an invocation that cannot take it exits 0 with
an info line, since overlapping cron ticks are expected); sweeps the inbox (or
ingests one PATH, copying it into ``sources/YYYY-MM/`` first when it lies
outside the vault); writes one trail at the end. Exit 1 when any source failed.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from buvis.pybase.filesystem import atomic_write_bytes
from buvis.pybase.result import CommandResult

from klyreon.backends import get_backend
from klyreon.backends.base import Backend
from klyreon.ingest.pipeline import SweepResult, sweep_sources
from klyreon.run.lock import LockBusyError, vault_lock
from klyreon.run.trail import write_trail
from klyreon.vault.git import GitIdentity, require_git_for_autonomy

__all__ = ["CommandIngest"]


class CommandIngest:
    """Run one bounded ingest over the inbox, or over a single PATH."""

    def __init__(  # noqa: PLR0913 - CLI-mirroring knobs, each with a configured default
        self,
        root: Path,
        *,
        path: Path | None = None,
        backend_name: str = "stub",
        model: str | None = None,
        max_sources: int = 5,
        timeout: int = 900,
        max_body_lines: int = 60,
        dry_run: bool = False,
        identity: GitIdentity | None = None,
        now: dt.datetime | None = None,
        backend: Backend | None = None,
    ) -> None:
        self.root = root
        self.path = path
        self.backend_name = backend_name
        self.model = model
        self.max_sources = max_sources
        self.timeout = timeout
        self.max_body_lines = max_body_lines
        self.dry_run = dry_run
        self.identity = identity or GitIdentity(name="klyreon", email="klyreon@localhost")
        self.now = now
        self._backend = backend

    def execute(self) -> CommandResult:
        gate = require_git_for_autonomy(self.root)
        if not gate.success:
            return CommandResult(success=False, error=gate.error)

        now = self.now or dt.datetime.now().astimezone()
        if self._backend is not None:
            backend: Backend = self._backend
        else:
            try:
                backend = get_backend(self.backend_name, model=self.model)
            except Exception as exc:  # surface any backend construction failure as a result
                return CommandResult(success=False, error=f"backend {self.backend_name!r} unavailable: {exc}")

        try:
            with vault_lock(self.root):
                return self._run(backend, now)
        except LockBusyError as exc:
            # Overlapping cron ticks are expected, not an error.
            return CommandResult(success=True, output=str(exc), info=["another run holds the lock; exiting cleanly"])

    def _run(self, backend: Backend, now: dt.datetime) -> CommandResult:
        only = self._prepare_single_source(now) if self.path is not None else None

        result = sweep_sources(
            self.root,
            backend=backend,
            identity=self.identity,
            now=now,
            max_sources=self.max_sources,
            timeout=self.timeout,
            max_body_lines=self.max_body_lines,
            dry_run=self.dry_run,
            only=only,
        )

        warnings = [w for o in (result.committed + result.failed + result.dry_run) for w in o.warnings]

        if self.dry_run:
            lines = [f"would ingest {o.source}: {len(o.zettels_created)} zettel(s)" for o in result.dry_run]
            return CommandResult(
                success=True,
                output="dry-run:\n" + "\n".join(lines) if lines else "dry-run: nothing to ingest",
                warnings=warnings,
                metadata={"dry_run": True, "count": len(result.dry_run)},
            )

        trail_rel: str | None = None
        if result.committed or result.failed:
            trail_rel, _ = write_trail(self.root, result, identity=self.identity, now=now)

        summary = self._summarise(result, trail_rel)
        return CommandResult(
            success=not result.any_failed,
            output=summary if not result.any_failed else None,
            error=summary if result.any_failed else None,
            warnings=warnings,
            metadata={
                "committed": len(result.committed),
                "failed": len(result.failed),
                "deferred": len(result.deferred),
                "trail": trail_rel,
            },
        )

    def _prepare_single_source(self, now: dt.datetime) -> str:
        """Return the vault-relative path for a single-PATH ingest.

        A path outside the vault is copied into ``sources/YYYY-MM/`` first.
        """
        if self.path is None:  # pragma: no cover - only called when path is set
            msg = "no path to prepare"
            raise ValueError(msg)
        resolved = self.path.expanduser().resolve()
        root_resolved = self.root.resolve()
        if root_resolved in resolved.parents:
            return resolved.relative_to(root_resolved).as_posix()
        # Outside the vault: copy into the current month's inbox.
        month = now.strftime("%Y-%m")
        dest_dir = self.root / "sources" / month
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / resolved.name
        atomic_write_bytes(dest, resolved.read_bytes())
        return dest.relative_to(root_resolved).as_posix()

    def _summarise(self, result: SweepResult, trail_rel: str | None) -> str:
        parts = [
            f"committed {len(result.committed)} source(s)",
            f"failed {len(result.failed)}",
            f"deferred {len(result.deferred)}",
        ]
        if trail_rel:
            parts.append(f"trail {trail_rel}")
        line = "; ".join(parts)
        if result.failed:
            detail = "\n".join(f"  {o.source}: {o.error}" for o in result.failed)
            return f"{line}\n{detail}"
        return line
