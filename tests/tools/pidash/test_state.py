from __future__ import annotations

import json

import pytest
from pidash.tui.state import DISPLAY_PHASES, parse_session_file, parse_state


class TestParseState:
    def test_valid_full_state(self, full_state_dict: dict) -> None:
        state = parse_state(json.dumps(full_state_dict))
        assert state is not None
        assert state.prd.name == "00010-split-ci"
        assert state.phase == "work"
        assert state.cycle == 2
        assert state.tasks_completed == 4
        assert state.tasks_total == 6
        assert len(state.autonomous_decisions) == 2
        assert len(state.deferred_decisions) == 1
        assert len(state.review_cycles) == 1

    def test_full_state_decision_fields(self, full_state_dict: dict) -> None:
        state = parse_state(json.dumps(full_state_dict))
        assert state is not None
        d = state.autonomous_decisions[1]
        assert d.action == "auto-fix"
        assert d.reason == "mechanical fix"
        assert d.cycle == 1
        dd = state.deferred_decisions[0]
        assert dd.consensus == "3/3"
        assert dd.reason == "touches public API"
        assert dd.status == "pending"

    def test_full_state_cycle_resolution_fields(self, full_state_dict: dict) -> None:
        state = parse_state(json.dumps(full_state_dict))
        assert state is not None
        rc = state.review_cycles[0]
        assert rc.issue_count == 3
        assert rc.auto_fixed == 2
        assert rc.escalated == 1
        assert rc.deferred == 0

    def test_full_state_batch(self, full_state_dict: dict) -> None:
        state = parse_state(json.dumps(full_state_dict))
        assert state is not None
        assert state.batch is not None
        assert state.batch.id == "202604011000"
        assert len(state.batch.completed_prds) == 1
        assert state.batch.completed_prds[0].filename == "00009-auth.md"
        assert state.batch.completed_prds[0].cycles == 2

    def test_full_state_timestamps(self, full_state_dict: dict) -> None:
        state = parse_state(json.dumps(full_state_dict))
        assert state is not None
        assert state.started_at == "2026-04-01T10:00:00Z"
        assert state.updated_at == "2026-04-01T10:30:00Z"

    def test_minimal_state(self, minimal_state_dict: dict) -> None:
        state = parse_state(json.dumps(minimal_state_dict))
        assert state is not None
        assert state.prd.name == "00010-split-ci"
        assert state.phase == "catchup"
        assert state.cycle == 0
        assert state.tasks_completed == 0
        assert state.tasks_total == 0
        assert state.autonomous_decisions == []
        assert state.deferred_decisions == []
        assert state.review_cycles == []

    def test_malformed_json_returns_none(self) -> None:
        assert parse_state("{invalid json") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_state("") is None

    def test_missing_required_field_returns_none(self) -> None:
        assert parse_state('{"phase": "work"}') is None

    def test_extra_fields_ignored(self, minimal_state_dict: dict) -> None:
        minimal_state_dict["unknown_field"] = "value"
        state = parse_state(json.dumps(minimal_state_dict))
        assert state is not None


class TestAutopilotFormat:
    """Parse autopilot JSON with nested severity dict in review_cycles."""

    def test_nested_severity_flattened(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        rc = state.review_cycles[0]
        assert rc.critical == 1
        assert rc.high == 2
        assert rc.medium == 1
        assert rc.low == 1

    def test_autopilot_decision_action_preserved(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        d = state.autonomous_decisions[0]
        assert d.action == "auto-fix"
        assert d.reason == "additive only"
        assert d.consensus == "2/3"
        assert d.cycle == 1

    def test_autopilot_deferred_status_preserved(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        d = state.deferred_decisions[0]
        assert d.status == "pending"
        assert d.reason == "touches public API"

    def test_autopilot_cycle_resolution_fields(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        rc = state.review_cycles[0]
        assert rc.issue_count == 5
        assert rc.auto_fixed == 3
        assert rc.escalated == 1
        assert rc.deferred == 1
        assert rc.recurring_issues == []

    def test_autopilot_timestamps(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        assert state.started_at == "2026-03-16T10:00:00Z"
        assert state.updated_at == "2026-03-16T10:30:00Z"

    def test_autopilot_research_on_decision(self) -> None:
        raw = json.dumps(
            {
                "prd": {"name": "test"},
                "phase": "review",
                "autonomous_decisions": [
                    {
                        "issue": "New dep: zod",
                        "severity": "high",
                        "action": "auto-fix",
                        "reason": "research-passed",
                        "research": {
                            "category": "new-dependency",
                            "verdict": "proceed",
                            "checks": [{"check": "license", "result": "MIT", "pass": True}],
                            "evidence_summary": "zod: MIT, active",
                        },
                    }
                ],
            }
        )
        state = parse_state(raw)
        assert state is not None
        d = state.autonomous_decisions[0]
        assert d.research is not None
        assert d.research["verdict"] == "proceed"
        assert d.research["category"] == "new-dependency"


class TestDisplayPhaseMapping:
    @pytest.mark.parametrize(
        ("phase", "expected"),
        [
            ("catchup", "CATCHUP"),
            ("planning", "PLANNING"),
            ("work", "WORKING"),
            ("rework", "WORKING"),
            ("review", "REVIEWING"),
            ("decision-gate", "REVIEWING"),
            ("paused", "REVIEWING"),
            ("doubt-review", "DOUBT"),
            ("done", "DONE"),
        ],
    )
    def test_phase_mapping(self, phase: str, expected: str) -> None:
        assert DISPLAY_PHASES.get(phase) == expected

    def test_unknown_phase_not_in_mapping(self) -> None:
        assert DISPLAY_PHASES.get("unknown") is None


class TestPrdStateDisplayPhase:
    def test_display_phase_property(self, minimal_state_dict: dict) -> None:
        minimal_state_dict["phase"] = "rework"
        state = parse_state(json.dumps(minimal_state_dict))
        assert state is not None
        assert state.display_phase == "WORKING"

    def test_display_phase_unknown_returns_phase(self, minimal_state_dict: dict) -> None:
        minimal_state_dict["phase"] = "mystery"
        state = parse_state(json.dumps(minimal_state_dict))
        assert state is not None
        assert state.display_phase == "MYSTERY"


class TestParseSessionFile:
    def test_valid_session_file(self, session_file_dict: dict) -> None:
        result = parse_session_file(json.dumps(session_file_dict))
        assert result is not None
        assert result.session_id == "abc123"
        assert result.cwd == "/Users/bob/git/src/github.com/buvis/gems"
        assert result.project_name == "gems"

    def test_project_name_from_cwd(self, session_file_dict: dict) -> None:
        session_file_dict["cwd"] = "/home/user/projects/my-cool-project"
        result = parse_session_file(json.dumps(session_file_dict))
        assert result is not None
        assert result.project_name == "my-cool-project"

    def test_inner_state_parsed(self, session_file_dict: dict) -> None:
        result = parse_session_file(json.dumps(session_file_dict))
        assert result is not None
        assert result.state is not None
        assert result.state.phase == "work"
        assert result.state.prd.name == "00016-foo"
        assert result.state.cycle == 1
        assert result.state.tasks_total == 5
        assert result.state.tasks_completed == 2

    def test_missing_session_id_returns_none(self, session_file_dict: dict) -> None:
        del session_file_dict["session_id"]
        assert parse_session_file(json.dumps(session_file_dict)) is None

    def test_malformed_json_returns_none(self) -> None:
        assert parse_session_file("{invalid json") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_session_file("") is None

    def test_updated_at_parsed(self, session_file_dict: dict) -> None:
        from datetime import datetime, timezone

        result = parse_session_file(json.dumps(session_file_dict))
        assert result is not None
        assert result.updated_at == datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_stopped_field_defaults_false(self, session_file_dict: dict) -> None:
        result = parse_session_file(json.dumps(session_file_dict))
        assert result is not None
        assert result.stopped is False

    def test_missing_prd_still_parses(self) -> None:
        raw = json.dumps({"session_id": "xyz789", "cwd": "/tmp/project"})
        result = parse_session_file(raw)
        assert result is not None
        assert result.session_id == "xyz789"
        assert result.cwd == "/tmp/project"
        assert result.project_name == "project"
        assert result.state is None
