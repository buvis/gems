from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from pidash.tui.app import PidashApp
from pidash.tui.watcher import SessionUpdated, StateChanged

TERMINAL_SIZES = [
    pytest.param((80, 24), id="80x24"),
    pytest.param((120, 40), id="120x40"),
    pytest.param((40, 15), id="40x15"),
]


def _rich_state_dict() -> dict:
    """State with 20+ tasks, decisions, and doubts for overflowing content."""
    tasks = []
    for i in range(25):
        if i < 10:
            status = "completed"
        elif i < 15:
            status = "in_progress"
        else:
            status = "pending"
        tasks.append({"id": str(i + 1), "name": f"Implement feature module {i + 1:02d}", "status": status})

    return {
        "prd": {
            "name": "00021-textual-screenshot-testing",
            "path": "dev/local/prds/wip/00021-textual-screenshot-testing.md",
        },
        "phase": "work",
        "phases_completed": ["catchup", "planning"],
        "cycle": 2,
        "tasks_total": 25,
        "tasks_completed": 10,
        "tasks": tasks,
        "autonomous_decisions": [
            {
                "issue": f"Auto-fix lint issue #{i}",
                "severity": "low" if i % 2 == 0 else "medium",
                "cycle": 1,
                "action": "auto-fix",
                "reason": "mechanical fix, additive only",
            }
            for i in range(5)
        ],
        "deferred_decisions": [
            {
                "issue": "Change public API shape for zettel search",
                "severity": "high",
                "cycle": 1,
                "consensus": "3/3",
                "reason": "touches public API contract",
                "status": "pending",
            },
            {
                "issue": "Migrate to async file watcher",
                "severity": "medium",
                "cycle": 2,
                "consensus": "2/3",
                "reason": "architectural change needed",
                "status": "pending",
            },
        ],
        "review_cycles": [
            {
                "cycle": 1,
                "issue_count": 8,
                "severity": {"critical": 0, "high": 2, "medium": 3, "low": 3},
                "auto_fixed": 5,
                "escalated": 1,
                "deferred": 2,
                "recurring_issues": [],
            },
        ],
        "doubts": [
            {
                "description": "Edge case: empty task list rendering",
                "category": "fix",
                "status": "resolved",
            },
            {
                "description": "Thread safety of file watcher callback",
                "category": "known",
                "justification": "Textual handles message posting thread-safely",
                "status": "pending",
            },
        ],
        "batch": {
            "id": "202604121400",
            "mode": "autopilot",
            "completed_prds": [
                {
                    "filename": "00020-fix-scrolling.md",
                    "cycles": 2,
                    "autonomous_decisions": 3,
                    "escalated_decisions": 0,
                },
            ],
        },
        "started_at": "2026-04-12T14:00:00Z",
        "updated_at": "2026-04-12T14:30:00Z",
    }


def _session_json(
    session_id: str,
    cwd: str,
    prd_name: str = "test-prd",
    phase: str = "work",
    needs_attention: bool = False,
    tasks_total: int = 5,
    tasks_completed: int = 2,
) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "cwd": cwd,
            "updated_at": "2026-04-12T14:00:00+00:00",
            "prd": {"name": prd_name},
            "phase": phase,
            "needs_attention": needs_attention,
            "tasks_total": tasks_total,
            "tasks_completed": tasks_completed,
            "tasks": [],
            "phases_completed": ["catchup", "planning"],
            "cycle": 1,
            "autonomous_decisions": [],
            "deferred_decisions": [],
            "doubts": [],
            "review_cycles": [],
        }
    )


def _kill_timers(app: PidashApp) -> None:
    """Disable spinner timers on pipeline and task widgets for deterministic output."""
    pipeline = app.query_one("#pipeline")
    pipeline._tick = MagicMock()
    tasks = app.query_one("#tasks")
    tasks._tick = MagicMock()


class TestPidashSingleProjectSnapshots:
    @pytest.mark.snapshot
    @pytest.mark.pidash
    @pytest.mark.parametrize("terminal_size", TERMINAL_SIZES)
    def test_single_project_with_many_tasks(self, snap_compare, tmp_path, terminal_size):
        state = _rich_state_dict()
        app = PidashApp(project_path=tmp_path, _watch=False)

        async def load_state(pilot):
            _kill_timers(app)
            await pilot.pause()
            app.post_message(StateChanged(json.dumps(state)))
            await pilot.pause()

        assert snap_compare(app, terminal_size=terminal_size, run_before=load_state)


class TestPidashMultiSessionSnapshots:
    @pytest.mark.snapshot
    @pytest.mark.pidash
    @pytest.mark.parametrize("terminal_size", TERMINAL_SIZES)
    def test_multi_session_with_many_sessions(self, snap_compare, terminal_size):
        app = PidashApp(_watch=False)

        projects = [
            ("gems", "00021-snapshot-tests", "work", False, 12, 5),
            ("homepage", "00005-redesign", "review", True, 8, 8),
            ("api-server", "00003-auth-refactor", "planning", False, 0, 0),
            ("docs-site", "00012-search", "work", False, 6, 3),
            ("ml-pipeline", "00007-gpu-batch", "done", False, 15, 15),
            ("infra", "00001-terraform-v2", "work", False, 20, 14),
            ("mobile-app", "00009-offline-mode", "review", True, 10, 9),
            ("analytics", "00004-dashboard", "catchup", False, 0, 0),
            ("data-lake", "00006-partitioning", "work", False, 7, 2),
            ("gateway", "00011-rate-limit", "blind-review", False, 4, 4),
            ("scheduler", "00008-cron-v2", "work", False, 9, 6),
            ("notifier", "00002-slack-bot", "doubt-review", False, 5, 5),
        ]

        async def load_sessions(pilot):
            _kill_timers(app)
            await pilot.pause()
            for i, (proj, prd, phase, attention, total, done) in enumerate(projects):
                sid = f"session-{i:02d}"
                app.post_message(
                    SessionUpdated(
                        sid,
                        _session_json(
                            sid,
                            f"/Users/bob/git/{proj}",
                            prd_name=prd,
                            phase=phase,
                            needs_attention=attention,
                            tasks_total=total,
                            tasks_completed=done,
                        ),
                    )
                )
            await pilot.pause()

        assert snap_compare(app, terminal_size=terminal_size, run_before=load_sessions)
