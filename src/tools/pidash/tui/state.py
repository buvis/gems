from __future__ import annotations

import json
import logging

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
    low: int = 0


class PrdInfo(BaseModel, frozen=True):
    name: str
    path: str = ""
    filename: str = ""


class PrdState(BaseModel):
    model_config = {"frozen": True, "extra": "ignore"}

    prd: PrdInfo
    phase: str
    phases_completed: list[str] = []
    cycle: int = 0
    tasks_completed: int = 0
    tasks_total: int = 0
    autonomous_decisions: list[Decision] = []
    deferred_decisions: list[Decision] = []
    review_cycles: list[CycleResult] = []
    done_prds: list[str] = []

    @property
    def display_phase(self) -> str:
        return DISPLAY_PHASES.get(self.phase, self.phase.upper())


def parse_state(raw: str) -> PrdState | None:
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
        return PrdState.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        logger.debug("Failed to parse prd-cycle.json", exc_info=True)
        return None
