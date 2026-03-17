from __future__ import annotations

import pytest


@pytest.fixture
def minimal_state_dict() -> dict:
    return {
        "prd": {"name": "00010-split-ci"},
        "phase": "catchup",
    }


@pytest.fixture
def full_state_dict() -> dict:
    return {
        "prd": {
            "name": "00010-split-ci",
            "path": ".local/prds/wip/00010-split-ci.md",
            "filename": "00010-split-ci.md",
        },
        "phase": "work",
        "phases_completed": ["catchup", "planning"],
        "cycle": 2,
        "tasks_completed": 4,
        "tasks_total": 6,
        "autonomous_decisions": [
            {"description": "skip lint fix", "severity": "low", "resolution": "auto-skipped"},
            {"description": "add missing dep", "severity": "medium", "resolution": "auto-added"},
        ],
        "deferred_decisions": [
            {"description": "change API contract?", "severity": "high", "resolution": "pending"},
        ],
        "review_cycles": [
            {"cycle": 1, "critical": 0, "high": 1, "low": 2},
        ],
        "done_prds": [],
    }
