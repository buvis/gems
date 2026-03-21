from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

DISPLAY_PHASES: dict[str, str] = {
    "catchup": "CATCHUP",
    "planning": "PLANNING",
    "work": "WORKING",
    "rework": "WORKING",
    "review": "REVIEWING",
    "decision-gate": "REVIEWING",
    "paused": "REVIEWING",
    "done": "DONE",
}

PHASE_ORDER: list[str] = ["CATCHUP", "PLANNING", "WORKING", "REVIEWING", "DONE"]


class Decision(BaseModel, frozen=True):
    description: str
    severity: str = "low"
    resolution: str = "pending"


class CycleResult(BaseModel, frozen=True):
    cycle: int
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class PrdInfo(BaseModel, frozen=True):
    name: str
    path: str = ""
    filename: str = ""


class TaskInfo(BaseModel, frozen=True):
    id: str = ""
    name: str
    status: str = "pending"


class PrdState(BaseModel):
    model_config = {"frozen": True, "extra": "ignore"}

    prd: PrdInfo
    phase: str
    needs_attention: bool = False
    phases_completed: list[str] = []
    cycle: int = 0
    tasks_completed: int = 0
    tasks_total: int = 0
    tasks: list[TaskInfo] = []
    autonomous_decisions: list[Decision] = []
    deferred_decisions: list[Decision] = []
    review_cycles: list[CycleResult] = []
    done_prds: list[str] = []

    @property
    def display_phase(self) -> str:
        return DISPLAY_PHASES.get(self.phase, self.phase.upper())


def _normalize_decisions(data: dict[str, Any]) -> None:
    for key in ("autonomous_decisions", "deferred_decisions"):
        normalized = []
        for d in data.get(key, []):
            if isinstance(d, str):
                normalized.append({"description": d})
            elif isinstance(d, dict):
                if "issue" in d and "description" not in d:
                    d["description"] = d.pop("issue")
                normalized.append(d)
        if key in data:
            data[key] = normalized


def _normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize autopilot JSON variants to PrdState schema."""
    prd = data.get("prd")
    if isinstance(prd, str):
        data["prd"] = {"name": prd, "path": data.pop("prd_path", "")}

    _normalize_decisions(data)

    tasks_normalized = []
    for t in data.get("tasks", []):
        if isinstance(t, str):
            tasks_normalized.append({"name": t})
        elif isinstance(t, dict):
            tasks_normalized.append(t)
    if "tasks" in data:
        data["tasks"] = tasks_normalized

    for rc in data.get("review_cycles", []):
        sev = rc.pop("severity", None)
        if isinstance(sev, dict):
            for k, v in sev.items():
                rc.setdefault(k, v)

    return data


def parse_state(raw: str) -> PrdState | None:
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
        _normalize_data(data)
        return PrdState.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        logger.debug("Failed to parse prd-cycle.json", exc_info=True)
        return None
