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
        result = HeaderBar().render_state(None)
        assert "no active PRD cycle" in result
        assert "watching" in result

    def test_with_state(self) -> None:
        state = _make_state()
        result = HeaderBar().render_state(state)
        assert "00010-test-prd" in result
        assert "cycle 1" in result

    def test_with_state_contains_time(self) -> None:
        state = _make_state()
        result = HeaderBar().render_state(state)
        # HH:MM:SS pattern
        import re

        assert re.search(r"\d{2}:\d{2}:\d{2}", result)

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
        assert "DONE" in result
        assert "[dim]" in result

    def test_active_phase_marked(self) -> None:
        state = _make_state(phase="work")
        result = PhasePipeline().render_state(state)
        assert "▸ WORKING" in result
        assert "on dark_green" in result

    def test_completed_phases_checked(self) -> None:
        state = _make_state(phase="work", phases_completed=["catchup", "planning"])
        result = PhasePipeline().render_state(state)
        assert "✓ CATCHUP" in result
        assert "✓ PLANNING" in result
        assert "[green]" in result

    def test_future_phases_dimmed(self) -> None:
        state = _make_state(phase="work", phases_completed=["catchup", "planning"])
        result = PhasePipeline().render_state(state)
        assert "✓ REVIEWING" not in result
        assert "▸ REVIEWING" not in result
        assert "[dim]" in result
        assert "REVIEWING" in result
        assert "DONE" in result

    def test_phases_separated(self) -> None:
        state = _make_state()
        result = PhasePipeline().render_state(state)
        assert "CATCHUP" in result
        assert "DONE" in result

    def test_doubt_phase_active(self) -> None:
        state = _make_state(
            phase="doubt-review",
            phases_completed=["catchup", "planning", "work", "review"],
        )
        result = PhasePipeline().render_state(state)
        assert "▸ DOUBT" in result
        assert "✓ REVIEWING" in result
        assert "DONE" in result

    def test_done_phase_all_checked(self) -> None:
        state = _make_state(
            phase="done",
            phases_completed=["catchup", "planning", "work", "review", "doubt-review"],
        )
        result = PhasePipeline().render_state(state)
        assert "✓ DONE" in result
        assert "✓ CATCHUP" in result
        assert "✓ DOUBT" in result
        assert "▸" not in result


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
        assert "No tasks yet" in TaskPanel().render_state(state)

    def test_shows_counts(self) -> None:
        state = _make_state(tasks_completed=3, tasks_total=5)
        result = TaskPanel().render_state(state)
        assert "3" in result
        assert "5" in result
        assert "2" in result

    def test_doubt_task_tagged(self) -> None:
        state = _make_state(
            tasks=[
                {"name": "[DOUBT] Fix edge case", "status": "pending"},
                {"name": "Normal task", "status": "completed"},
            ],
            tasks_total=2,
            tasks_completed=1,
        )
        result = TaskPanel().render_state(state)
        assert "\\[DOUBT]" in result
        assert "[cyan]" in result
        assert "Fix edge case" in result
        assert "Normal task" in result

    def test_doubt_task_completed_dimmed(self) -> None:
        state = _make_state(
            tasks=[{"name": "[DOUBT] Fix edge case", "status": "completed"}],
            tasks_total=1,
            tasks_completed=1,
        )
        result = TaskPanel().render_state(state)
        assert "\\[DOUBT]" in result
        assert "[dim]" in result

    def test_cycle_task_tagged(self) -> None:
        state = _make_state(
            tasks=[
                {"name": "[C1] Fix blob test", "status": "pending"},
                {"name": "[C2] Update docs", "status": "in_progress"},
                {"name": "Original task", "status": "completed"},
            ],
            tasks_total=3,
            tasks_completed=1,
        )
        result = TaskPanel().render_state(state)
        assert "\\[C1]" in result
        assert "\\[C2]" in result
        assert "[magenta]" in result
        assert "Fix blob test" in result
        assert "Update docs" in result
        assert "Original task" in result

    def test_cycle_task_completed_dimmed(self) -> None:
        state = _make_state(
            tasks=[{"name": "[C1] Fix issue", "status": "completed"}],
            tasks_total=1,
            tasks_completed=1,
        )
        result = TaskPanel().render_state(state)
        assert "\\[C1]" in result
        assert "[dim]" in result

    def test_brackets_in_name_escaped(self) -> None:
        state = _make_state(
            tasks=[{"name": "Fix [important] bug", "status": "pending"}],
            tasks_total=1,
            tasks_completed=0,
        )
        result = TaskPanel().render_state(state)
        assert "\\[important]" in result


class TestDecisionPanel:
    def test_none_state_returns_empty(self) -> None:
        assert DecisionPanel().render_state(None) == ""

    def test_auto_decision_prefix(self) -> None:
        state = _make_state()
        result = DecisionPanel().render_state(state)
        assert "AUTO-APPROVED" in result or "AUTO-REJECTED" in result

    def test_auto_decision_colored_by_severity(self) -> None:
        state = _make_state()
        result = DecisionPanel().render_state(state)
        assert "[green]" in result  # low severity

    def test_pending_decision_prefix(self) -> None:
        state = _make_state()
        result = DecisionPanel().render_state(state)
        assert "⚠ PENDING: change API?" in result

    def test_pending_decision_bold(self) -> None:
        state = _make_state()
        result = DecisionPanel().render_state(state)
        assert "[bold orange1]" in result  # high severity, bold

    def test_no_decisions(self) -> None:
        state = _make_state(autonomous_decisions=[], deferred_decisions=[])
        result = DecisionPanel().render_state(state)
        assert result == ""

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

    def test_omits_zero_counts(self) -> None:
        state = _make_state()
        result = CyclePanel().render_state(state)
        assert "0 low" not in result

    def test_severity_colored(self) -> None:
        state = _make_state()
        result = CyclePanel().render_state(state)
        assert "[red]" in result  # critical
        assert "[orange1]" in result  # high

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
        fb = FooterBar()
        assert callable(fb.render_content)
