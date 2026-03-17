from __future__ import annotations

from datetime import datetime

from rich.text import Text

from pidash.tui.state import DISPLAY_PHASES, PHASE_ORDER, PrdState


class HeaderBar:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return "pidash │ no active PRD cycle │ watching..."
        now = datetime.now().strftime("%H:%M:%S")
        return f"pidash │ {state.prd.name} │ cycle {state.cycle} │ updated {now}"


class PhasePipeline:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return " → ".join(f"  {phase}" for phase in PHASE_ORDER)

        active = DISPLAY_PHASES.get(state.phase, state.phase.upper())
        completed_display = {DISPLAY_PHASES.get(p, p.upper()) for p in state.phases_completed}

        parts: list[str] = []
        for phase in PHASE_ORDER:
            if phase == active:
                parts.append(f"▸ {phase}")
            elif phase in completed_display:
                parts.append(f"✓ {phase}")
            else:
                parts.append(f"  {phase}")
        return " → ".join(parts)


class ProgressSection:
    def render_state(self, state: PrdState | None) -> str:
        if state is None or state.tasks_total == 0:
            return ""
        bar_len = 30
        filled = min(round(bar_len * state.tasks_completed / state.tasks_total), bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        return f"Tasks {bar} {state.tasks_completed}/{state.tasks_total}"


class TaskPanel:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        if state.tasks_total == 0:
            return "No tasks yet"
        remaining = state.tasks_total - state.tasks_completed
        return f"completed {state.tasks_completed}  remaining {remaining}  total {state.tasks_total}"


class DecisionPanel:
    _severity_colors: dict[str, str] = {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "green",
    }

    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        lines: list[str] = []
        for d in state.autonomous_decisions:
            lines.append(f"AUTO {d.description}")
        for d in state.deferred_decisions:
            lines.append(f"⚠ PENDING: {d.description}")
        return "\n".join(lines)

    def render_rich(self, state: PrdState | None) -> Text:
        text = Text()
        if state is None:
            return text
        for d in state.autonomous_decisions:
            color = self._severity_colors.get(d.severity, "white")
            text.append(f"AUTO {d.description}\n", style=color)
        for d in state.deferred_decisions:
            color = self._severity_colors.get(d.severity, "white")
            text.append(f"⚠ PENDING: {d.description}\n", style=f"bold {color}")
        return text


class CyclePanel:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        if not state.review_cycles:
            return ""
        lines: list[str] = []
        for c in state.review_cycles:
            lines.append(f"C{c.cycle}  {c.critical} crit  {c.high} high  {c.low} low")
        return "\n".join(lines)


class FooterBar:
    def render_content(self) -> str:
        return "q quit │ r refresh │ watching .local/prd-cycle.json"
