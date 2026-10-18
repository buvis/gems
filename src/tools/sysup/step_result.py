from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["RED", "Kind", "Status", "StepResult"]

Status = Literal["ok", "failed", "expiring", "expired", "unknown", "warned"]
Kind = Literal["command", "item"]
RED: frozenset[str] = frozenset({"failed", "expired", "unknown"})


@dataclass(frozen=True)
class StepResult:
    """One reported step.

    ``status`` defaults from ``success`` (``ok`` / ``failed``); an expiry check
    (PRD 00096) passes ``expiring``, ``expired`` or ``unknown`` explicitly.
    ``command`` names the config entry that produced the step; the runner
    stamps it. ``kind`` tells a command entry from an expiry item.
    """

    label: str
    success: bool
    message: str = ""
    status: Status = "ok"
    command: str = ""
    kind: Kind = "command"

    def __post_init__(self) -> None:
        if not self.success and self.status == "ok":
            object.__setattr__(self, "status", "failed")
