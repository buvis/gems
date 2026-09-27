from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from backup.capabilities import CAPABILITIES
from backup.step_result import StepResult

if TYPE_CHECKING:
    from collections.abc import Iterator

    from backup.config import BackupConfig, BackupInstance

__all__ = ["Runner"]


class Runner:
    """Execute selected backup instances, yielding a :class:`StepResult` per step.

    Each instance invokes its registered capability with the instance's ``with:``
    inputs plus the runtime context the capability needs: the resolved global
    ``excludes`` list, the instance ``label``, and the ``dry_run`` flag. Under
    ``dry_run`` the capability itself previews (walks + reports) without writing.
    """

    def __init__(self: Runner, cfg: BackupConfig, *, dry_run: bool = False) -> None:
        self._cfg = cfg
        self._dry_run = dry_run

    def run(self: Runner, selected: list[tuple[str, BackupInstance]]) -> Iterator[StepResult]:
        for name, instance in selected:
            yield from self._run_instance(name, instance)

    def _run_instance(self: Runner, name: str, instance: BackupInstance) -> Iterator[StepResult]:
        capability = CAPABILITIES.get(instance.use)
        if capability is None:  # pragma: no cover - load_config validates this
            yield StepResult(name, success=False, message=f"unknown capability '{instance.use}'")
            return

        call_kwargs: dict[str, object] = {
            **instance.with_,
            "label": name,
            "excludes": list(self._cfg.excludes),
            "dry_run": self._dry_run,
        }
        try:
            yield from capability.run(**call_kwargs)
        except FatalError:
            raise
        except Exception as exc:
            yield StepResult(name, success=False, message=f"{name} failed: {exc}")
