from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError, model_validator

logger = logging.getLogger(__name__)

DISPLAY_PHASES: dict[str, str] = {
    "catchup": "CATCHUP",
    "planning": "PLANNING",
    "work": "WORKING",
    "rework": "WORKING",
    "review": "REVIEWING",
    "decision-gate": "REVIEWING",
    "paused": "REVIEWING",
    "doubt-review": "DOUBT",
    "done": "DONE",
}

PHASE_ORDER: list[str] = ["CATCHUP", "PLANNING", "WORKING", "REVIEWING", "DOUBT", "DONE"]


class Decision(BaseModel, frozen=True):
    issue: str
    severity: str = "low"
    cycle: int = 0
    consensus: str = ""
    action: str = ""
    reason: str = ""
    status: str = ""
    research: dict[str, Any] | None = None


class Doubt(BaseModel, frozen=True):
    description: str
    severity: str = "medium"
    status: str = "pending"


class CycleResult(BaseModel, frozen=True):
    cycle: int
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    issue_count: int = 0
    auto_fixed: int = 0
    escalated: int = 0
    deferred: int = 0
    recurring_issues: list[str] = []


class PrdInfo(BaseModel, frozen=True):
    name: str
    path: str = ""
    filename: str = ""


class BatchPrdInfo(BaseModel, frozen=True):
    filename: str
    cycles: int = 0
    autonomous_decisions: int = 0
    escalated_decisions: int = 0


class BatchInfo(BaseModel, frozen=True):
    id: str = ""
    mode: str = "autopilot"
    completed_prds: list[BatchPrdInfo] = []


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
    doubts: list[Doubt] = []
    review_cycles: list[CycleResult] = []
    batch: BatchInfo | None = None
    started_at: str = ""
    updated_at: str = ""

    @property
    def display_phase(self) -> str:
        return DISPLAY_PHASES.get(self.phase, self.phase.upper())


def _flatten_review_cycle_severity(data: dict[str, Any]) -> None:
    for rc in data.get("review_cycles", []):
        sev = rc.pop("severity", None)
        if isinstance(sev, dict):
            for k, v in sev.items():
                rc.setdefault(k, v)


def parse_state(raw: str) -> PrdState | None:
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
        _flatten_review_cycle_severity(data)
        return PrdState.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        logger.debug("Failed to parse state.json", exc_info=True)
        return None


class SessionState(BaseModel):
    model_config = {"frozen": True}

    session_id: str
    cwd: str
    project_name: str = ""
    state: PrdState | None = None
    stopped: bool = False
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _compute_project_name(cls, values: Any) -> Any:
        if isinstance(values, dict) and not values.get("project_name"):
            cwd = values.get("cwd", "")
            values["project_name"] = Path(cwd).name if cwd else ""
        return values


def parse_session_file(raw: str) -> SessionState | None:
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    session_id = data.get("session_id")
    if not session_id:
        return None

    cwd = data.get("cwd", "")
    updated_at = data.get("updated_at")
    stopped = data.get("stopped", False)

    inner_state: PrdState | None = None
    if "prd" in data and "phase" in data:
        inner_state = parse_state(raw)

    try:
        return SessionState(
            session_id=session_id,
            cwd=cwd,
            state=inner_state,
            stopped=stopped,
            updated_at=updated_at,
        )
    except ValidationError:
        logger.debug("Failed to parse session file", exc_info=True)
        return None
