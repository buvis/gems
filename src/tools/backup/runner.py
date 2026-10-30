from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from buvis.pybase.result import FatalError

from backup.capabilities import CAPABILITIES
from backup.config import effective_excludes
from backup.step_result import PlanEntry, StepResult

if TYPE_CHECKING:
    from collections.abc import Iterator

    from backup.config import BackupConfig, BackupInstance

__all__ = ["Runner"]


class Runner:
    """Execute selected backup instances, yielding a :class:`StepResult` per step.

    Each instance invokes its registered capability with the instance's ``with:``
    inputs plus the runtime context the capability needs: the resolved instance
    ``excludes`` list, the instance ``label``, and the ``dry_run`` flag. Under
    ``dry_run`` the capability itself previews (walks + reports) without writing.
    """

    def __init__(self: Runner, cfg: BackupConfig, *, dry_run: bool = False) -> None:
        self._cfg = cfg
        self._dry_run = dry_run

    def run(self: Runner, selected: list[tuple[str, BackupInstance]]) -> Iterator[StepResult]:
        now = datetime.now()
        entries = self._plan(selected, now)
        for (name, instance), entry in zip(selected, entries, strict=True):
            if entry.status == "fail":
                yield StepResult(name, success=False, message=entry.reason)
            else:
                yield from self._run_instance(name, instance, now)

    def plan(self: Runner, selected: list[tuple[str, BackupInstance]]) -> list[PlanEntry]:
        return self._plan(selected, datetime.now())

    def _plan(self: Runner, selected: list[tuple[str, BackupInstance]], now: datetime) -> list[PlanEntry]:
        entries = []
        keys: list[str | None] = []
        outputs: dict[str, list[str]] = {}
        for name, instance in selected:
            capability = CAPABILITIES.get(instance.use)
            key: str | None = None
            if capability is None:  # pragma: no cover - load_config validates this
                entry = PlanEntry(name, "", "", "fail", f"unknown capability '{instance.use}'", False)
            else:
                call_kwargs: dict[str, object] = {
                    **instance.with_,
                    "label": name,
                    "excludes": list(effective_excludes(self._cfg, instance)),
                    "now": now,
                }
                try:
                    entry = capability.plan(**call_kwargs)
                except FatalError:
                    raise
                except Exception as exc:
                    # keep the configured output so duplicate detection still sees it
                    # (resolved with the run-wide timestamp, like the capability does)
                    configured = now.strftime(str(instance.with_.get("out", "")))
                    entry = PlanEntry(name, "", configured, "fail", f"{name} failed: {exc}", False)
                if entry.out:
                    key = os.path.normpath(os.path.expanduser(entry.out))
                    outputs.setdefault(key, []).append(name)
            entries.append(entry)
            keys.append(key)

        for index, (entry, out) in enumerate(zip(entries, keys, strict=True)):
            if out is not None and len(outputs[out]) > 1:
                names = outputs[out]
                others = ", ".join(sorted(name for name in names if name != entry.label))
                entries[index] = entry._replace(
                    out=out,
                    status="fail",
                    reason=f"output '{out}' is also the output of '{others}'",
                )
        return entries

    def _run_instance(self: Runner, name: str, instance: BackupInstance, now: datetime) -> Iterator[StepResult]:
        capability = CAPABILITIES[instance.use]

        call_kwargs: dict[str, object] = {
            **instance.with_,
            "label": name,
            "excludes": list(effective_excludes(self._cfg, instance)),
            "dry_run": self._dry_run,
            "now": now,
        }
        try:
            yield from capability.run(**call_kwargs)
        except FatalError:
            raise
        except Exception as exc:
            yield StepResult(name, success=False, message=f"{name} failed: {exc}")
