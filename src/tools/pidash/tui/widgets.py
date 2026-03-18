from __future__ import annotations

from datetime import datetime

from pidash.tui.state import DISPLAY_PHASES, PHASE_ORDER, PrdState


class HeaderBar:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return "[dim]no active PRD cycle — watching...[/dim]"
        now = datetime.now().strftime("%H:%M:%S")
        return f" [bold]{state.prd.name}[/bold]  cycle {state.cycle}  {now} "


class PhasePipeline:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return "  ".join(f"[dim]  {phase}  [/dim]" for phase in PHASE_ORDER)

        active = DISPLAY_PHASES.get(state.phase, state.phase.upper())
        active_idx = PHASE_ORDER.index(active) if active in PHASE_ORDER else len(PHASE_ORDER)
        completed_display = {DISPLAY_PHASES.get(p, p.upper()) for p in state.phases_completed}
        all_done = active == "DONE"

        parts: list[str] = []
        for i, phase in enumerate(PHASE_ORDER):
            if all_done or (phase in completed_display and i < active_idx):
                parts.append(f"[green] ✓ {phase} [/green]")
            elif phase == active:
                parts.append(f"[bold white on dark_green] ▸ {phase} [/bold white on dark_green]")
            else:
                parts.append(f"[dim]   {phase}  [/dim]")
        return "  ".join(parts)


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
            return "[dim]No tasks yet[/dim]"
        remaining = state.tasks_total - state.tasks_completed
        return f"completed {state.tasks_completed}  remaining {remaining}  total {state.tasks_total}"


class DecisionPanel:
    _severity_colors: dict[str, str] = {
        "critical": "red",
        "high": "orange1",
        "medium": "yellow",
        "low": "green",
    }

    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        lines: list[str] = []
        for d in state.autonomous_decisions:
            color = self._severity_colors.get(d.severity, "dim")
            lines.append(f"[{color}]AUTO {d.description}[/{color}]")
        for d in state.deferred_decisions:
            color = self._severity_colors.get(d.severity, "red")
            lines.append(f"[bold {color}]⚠ PENDING: {d.description}[/bold {color}]")
        return "\n".join(lines)


class CyclePanel:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        if not state.review_cycles:
            return ""
        lines: list[str] = []
        for c in state.review_cycles:
            parts = [f"C{c.cycle}"]
            if c.critical:
                parts.append(f"[red]{c.critical} crit[/red]")
            if c.high:
                parts.append(f"[orange1]{c.high} high[/orange1]")
            if c.medium:
                parts.append(f"[yellow]{c.medium} med[/yellow]")
            if c.low:
                parts.append(f"[green]{c.low} low[/green]")
            lines.append("  ".join(parts))
        return "\n".join(lines)


class FooterBar:
    def render_content(self) -> str:
        return "q quit │ r refresh │ watching .local/prd-cycle.json"
