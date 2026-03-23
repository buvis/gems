from __future__ import annotations

import json

import pytest
from pidash.tui.state import DISPLAY_PHASES, parse_state


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
    """Parse the actual autopilot JSON format (string prd, issue field, nested severity)."""

    def test_string_prd_normalized(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        assert state.prd.name == "00002-add-feature"
        assert state.prd.path == ".local/prds/wip/00002-add-feature.md"

    def test_issue_mapped_to_description(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        assert state.autonomous_decisions[0].description == "Null check missing"
        assert state.deferred_decisions[0].description == "Change API contract?"

    def test_nested_severity_flattened(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        rc = state.review_cycles[0]
        assert rc.critical == 1
        assert rc.high == 2
        assert rc.medium == 1
        assert rc.low == 1

    def test_extra_autopilot_fields_ignored(self, autopilot_state_dict: dict) -> None:
        state = parse_state(json.dumps(autopilot_state_dict))
        assert state is not None
        assert state.phase == "review"
        assert state.cycle == 1

    def test_minimal_string_prd(self) -> None:
        raw = json.dumps({"prd": "my-prd", "phase": "catchup"})
        state = parse_state(raw)
        assert state is not None
        assert state.prd.name == "my-prd"
        assert state.prd.path == ""


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
