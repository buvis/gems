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
            {
                "issue": "skip lint fix",
                "severity": "low",
                "cycle": 1,
                "action": "skip",
                "reason": "non-blocking lint issue",
            },
            {
                "issue": "add missing dep",
                "severity": "medium",
                "cycle": 1,
                "action": "auto-fix",
                "reason": "mechanical fix",
            },
        ],
        "deferred_decisions": [
            {
                "issue": "change API contract?",
                "severity": "high",
                "cycle": 1,
                "consensus": "3/3",
                "reason": "touches public API",
                "status": "pending",
            },
        ],
        "review_cycles": [
            {
                "cycle": 1,
                "critical": 0,
                "high": 1,
                "low": 2,
                "issue_count": 3,
                "auto_fixed": 2,
                "escalated": 1,
                "deferred": 0,
            },
        ],
        "batch": {
            "id": "202604011000",
            "mode": "autopilot",
            "completed_prds": [
                {"filename": "00009-auth.md", "cycles": 2, "autonomous_decisions": 3, "escalated_decisions": 0},
            ],
        },
        "started_at": "2026-04-01T10:00:00Z",
        "updated_at": "2026-04-01T10:30:00Z",
    }


@pytest.fixture
def session_file_dict() -> dict:
    return {
        "session_id": "abc123",
        "cwd": "/Users/bob/git/src/github.com/buvis/gems",
        "updated_at": "2026-04-01T12:00:00+00:00",
        "prd": {"name": "00016-foo", "path": "dev/local/prds/wip/00016-foo.md"},
        "phase": "work",
        "phases_completed": ["catchup", "planning"],
        "cycle": 1,
        "tasks_total": 5,
        "tasks_completed": 2,
        "tasks": [],
        "needs_attention": False,
        "autonomous_decisions": [],
        "deferred_decisions": [],
        "doubts": [],
        "review_cycles": [],
    }


@pytest.fixture
def autopilot_state_dict() -> dict:
    """Autopilot JSON with nested severity dict in review_cycles."""
    return {
        "prd": {
            "name": "00002-add-feature",
            "path": "dev/local/prds/wip/00002-add-feature.md",
            "filename": "00002-add-feature.md",
        },
        "phase": "review",
        "phases_completed": ["catchup", "planning", "work"],
        "cycle": 1,
        "autonomous_decisions": [
            {
                "cycle": 1,
                "issue": "Null check missing",
                "severity": "critical",
                "consensus": "2/3",
                "action": "auto-fix",
                "reason": "additive only",
            },
        ],
        "deferred_decisions": [
            {
                "cycle": 1,
                "issue": "Change API contract?",
                "severity": "high",
                "consensus": "3/3",
                "reason": "touches public API",
                "status": "pending",
            },
        ],
        "review_cycles": [
            {
                "cycle": 1,
                "issue_count": 5,
                "severity": {"critical": 1, "high": 2, "medium": 1, "low": 1},
                "auto_fixed": 3,
                "escalated": 1,
                "deferred": 1,
                "recurring_issues": [],
            },
        ],
        "started_at": "2026-03-16T10:00:00Z",
        "updated_at": "2026-03-16T10:30:00Z",
    }
