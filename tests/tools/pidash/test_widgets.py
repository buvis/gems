from __future__ import annotations

import json

from pidash.tui.state import PrdState, parse_state
from pidash.tui.widgets import (
    CyclePanel,
    DecisionPanel,
    FooterBar,
    HeaderBar,
    PhasePipeline,
    ProgressSection,
    TaskPanel,
)


def _make_state(phase: str = "work", **overrides) -> PrdState:
    data = {
        "prd": {"name": "00010-test-prd"},
        "phase": phase,
        "phases_completed": ["catchup", "planning"],
        "cycle": 1,
        "tasks_completed": 3,
        "tasks_total": 5,
        "autonomous_decisions": [
            {"description": "skip lint", "severity": "low", "resolution": "auto"},
        ],
        "deferred_decisions": [
            {"description": "change API?", "severity": "high", "resolution": "pending"},
        ],
        "review_cycles": [
            {"cycle": 1, "critical": 1, "high": 2, "low": 0},
        ],
    }
    data.update(overrides)
    result = parse_state(json.dumps(data))
    assert result is not None
    return result


class TestHeaderBar:
    def test_none_state(self) -> None:
        assert HeaderBar().render_state(None) == "pidash │ no active PRD cycle │ watching..."

    def test_with_state(self) -> None:
        state = _make_state()
        result = HeaderBar().render_state(state)
        assert result.startswith("pidash │ 00010-test-prd │ cycle 1 │ updated ")

    def test_with_state_contains_time(self) -> None:
        state = _make_state()
        result = HeaderBar().render_state(state)
        # updated HH:MM:SS — colon-separated digits
        parts = result.split("│")
        assert len(parts) == 4
        time_part = parts[3].strip()
        assert time_part.startswith("updated ")
        time_str = time_part[len("updated ") :]
        assert len(time_str) == 8
        assert time_str[2] == ":" and time_str[5] == ":"

    def test_cycle_number_reflects_state(self) -> None:
        state = _make_state(cycle=3)
        result = HeaderBar().render_state(state)
        assert "cycle 3" in result

    def test_prd_name_in_header(self) -> None:
        state = _make_state()
        result = HeaderBar().render_state(state)
        assert "00010-test-prd" in result


class TestPhasePipeline:
    def test_none_state_all_dimmed(self) -> None:
        result = PhasePipeline().render_state(None)
        assert "▸" not in result
        assert "✓" not in result
        assert "CATCHUP" in result
        assert "PLANNING" in result
        assert "WORKING" in result
        assert "REVIEWING" in result
        assert "DONE" in result

    def test_active_phase_marked(self) -> None:
        state = _make_state(phase="work")
        result = PhasePipeline().render_state(state)
        assert "▸ WORKING" in result

    def test_completed_phases_checked(self) -> None:
        state = _make_state(phase="work", phases_completed=["catchup", "planning"])
        result = PhasePipeline().render_state(state)
        assert "✓ CATCHUP" in result
        assert "✓ PLANNING" in result

    def test_future_phases_plain(self) -> None:
        state = _make_state(phase="work", phases_completed=["catchup", "planning"])
        result = PhasePipeline().render_state(state)
        # REVIEWING and DONE should have no marker prefix
        assert "✓ REVIEWING" not in result
        assert "▸ REVIEWING" not in result
        assert "✓ DONE" not in result
        assert "▸ DONE" not in result

    def test_phases_joined_by_arrow(self) -> None:
        state = _make_state()
        result = PhasePipeline().render_state(state)
        assert " → " in result

    def test_done_phase(self) -> None:
        state = _make_state(
            phase="done",
            phases_completed=["catchup", "planning", "work", "review"],
        )
        result = PhasePipeline().render_state(state)
        assert "▸ DONE" in result


class TestProgressSection:
    def test_none_state_returns_empty(self) -> None:
        assert ProgressSection().render_state(None) == ""

    def test_zero_total_returns_empty(self) -> None:
        state = _make_state(tasks_total=0, tasks_completed=0)
        assert ProgressSection().render_state(state) == ""

    def test_bar_present(self) -> None:
        state = _make_state(tasks_completed=3, tasks_total=5)
        result = ProgressSection().render_state(state)
        assert "Tasks" in result
        assert "3/5" in result
        assert "█" in result
        assert "░" in result

    def test_bar_length_30(self) -> None:
        state = _make_state(tasks_completed=3, tasks_total=5)
        result = ProgressSection().render_state(state)
        # Extract bar characters
        bar_chars = [c for c in result if c in ("█", "░")]
        assert len(bar_chars) == 30

    def test_full_completion(self) -> None:
        state = _make_state(tasks_completed=5, tasks_total=5)
        result = ProgressSection().render_state(state)
        assert "░" not in result
        bar_chars = [c for c in result if c in ("█", "░")]
        assert len(bar_chars) == 30

    def test_zero_completion(self) -> None:
        state = _make_state(tasks_completed=0, tasks_total=5)
        result = ProgressSection().render_state(state)
        assert "█" not in result


class TestTaskPanel:
    def test_none_state_returns_empty(self) -> None:
        assert TaskPanel().render_state(None) == ""

    def test_zero_tasks_returns_no_tasks_yet(self) -> None:
        state = _make_state(tasks_total=0, tasks_completed=0)
        assert TaskPanel().render_state(state) == "No tasks yet"

    def test_shows_counts(self) -> None:
        state = _make_state(tasks_completed=3, tasks_total=5)
        result = TaskPanel().render_state(state)
        assert "3" in result
        assert "5" in result
        # remaining = 2
        assert "2" in result


class TestDecisionPanel:
    def test_none_state_returns_empty(self) -> None:
        assert DecisionPanel().render_state(None) == ""

    def test_auto_decision_prefix(self) -> None:
        state = _make_state()
        result = DecisionPanel().render_state(state)
        assert "AUTO skip lint" in result

    def test_pending_decision_prefix(self) -> None:
        state = _make_state()
        result = DecisionPanel().render_state(state)
        assert "⚠ PENDING: change API?" in result

    def test_no_decisions(self) -> None:
        state = _make_state(autonomous_decisions=[], deferred_decisions=[])
        result = DecisionPanel().render_state(state)
        assert result == ""

    def test_render_rich_returns_text_object(self) -> None:
        from rich.text import Text

        state = _make_state()
        result = DecisionPanel().render_rich(state)
        assert isinstance(result, Text)

    def test_render_rich_none_returns_text_object(self) -> None:
        from rich.text import Text

        result = DecisionPanel().render_rich(None)
        assert isinstance(result, Text)

    def test_severity_colors_dict_exists(self) -> None:
        panel = DecisionPanel()
        assert hasattr(panel, "_severity_colors")
        assert isinstance(panel._severity_colors, dict)
        assert "low" in panel._severity_colors
        assert "high" in panel._severity_colors
        assert "critical" in panel._severity_colors


class TestCyclePanel:
    def test_none_state_returns_empty(self) -> None:
        assert CyclePanel().render_state(None) == ""

    def test_shows_cycle_data(self) -> None:
        state = _make_state()
        result = CyclePanel().render_state(state)
        assert "C1" in result
        assert "1 crit" in result
        assert "2 high" in result
        assert "0 low" in result

    def test_multiple_cycles(self) -> None:
        state = _make_state(
            review_cycles=[
                {"cycle": 1, "critical": 0, "high": 1, "low": 2},
                {"cycle": 2, "critical": 1, "high": 0, "low": 0},
            ]
        )
        result = CyclePanel().render_state(state)
        assert "C1" in result
        assert "C2" in result

    def test_no_cycles(self) -> None:
        state = _make_state(review_cycles=[])
        assert CyclePanel().render_state(state) == ""


class TestFooterBar:
    def test_render_content(self) -> None:
        result = FooterBar().render_content()
        assert result == "q quit │ r refresh │ watching .local/prd-cycle.json"

    def test_render_content_no_state_arg(self) -> None:
        # FooterBar.render_content takes no state
        fb = FooterBar()
        assert callable(fb.render_content)
