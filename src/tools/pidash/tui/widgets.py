from __future__ import annotations

import re
from datetime import datetime

from pidash.tui.state import DISPLAY_PHASES, PHASE_ORDER, PrdState, SessionState

_CYCLE_RE = re.compile(r"^\[C(\d+)\] ")
_DECISION_RE = re.compile(r"^\[D(\d+)\] ")


class HeaderBar:
    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return "[dim]no active PRD cycle — watching...[/dim]"
        now = datetime.now().strftime("%H:%M:%S")
        batch = ""
        if state.batch and state.batch.completed_prds:
            n = len(state.batch.completed_prds)
            batch = f"  [dim]{n} PRDs done[/dim]"
        return f"[bold reverse] {state.prd.name} [/bold reverse]  cycle {state.cycle}  {now}{batch}"


class PhasePipeline:
    def __init__(self) -> None:
        self._header = HeaderBar()
        self._progress = ProgressSection()
        self.spinner: str = "▸"

    def render_state(self, state: PrdState | None) -> str:
        header = self._header.render_state(state)
        progress = self._progress.render_state(state)

        if state is None:
            phases = "  ".join(f"[dim]  {phase}  [/dim]" for phase in PHASE_ORDER)
            return f"{header}\n\n{phases}"

        active = DISPLAY_PHASES.get(state.phase, state.phase.upper())
        active_idx = PHASE_ORDER.index(active) if active in PHASE_ORDER else len(PHASE_ORDER)
        completed_display = {DISPLAY_PHASES.get(p, p.upper()) for p in state.phases_completed}
        all_done = active == "DONE"

        parts: list[str] = []
        for i, phase in enumerate(PHASE_ORDER):
            if all_done or (phase in completed_display and i < active_idx):
                parts.append(f"[green] ✓ {phase} [/green]")
            elif phase == active:
                parts.append(f"[bold white on dark_green] {self.spinner} {phase} [/bold white on dark_green]")
            else:
                parts.append(f"[dim]   {phase}  [/dim]")
        phases = "  ".join(parts)
        lines = [header, "", phases]
        if progress:
            lines.extend(["", progress])
        return "\n".join(lines)


class ProgressSection:
    def render_state(self, state: PrdState | None) -> str:
        if state is None or state.tasks_total == 0:
            return ""
        bar_len = 30
        filled = min(round(bar_len * state.tasks_completed / state.tasks_total), bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        return f"Tasks {bar} {state.tasks_completed}/{state.tasks_total}"


class TaskPanel:
    _status_markers: dict[str, str] = {
        "completed": "[green]✓[/green]",
        "pending": "[dim]·[/dim]",
    }
    _DOUBT_PREFIX = "[DOUBT] "

    def __init__(self) -> None:
        self.spinner: str = "▸"

    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        if not state.tasks and state.tasks_total == 0:
            return "[dim]No tasks yet[/dim]"
        if state.tasks:
            lines: list[str] = []
            for t in state.tasks:
                if t.status == "in_progress":
                    marker = f"[bold yellow]{self.spinner}[/bold yellow]"
                else:
                    marker = self._status_markers.get(t.status, "[dim]·[/dim]")
                name = t.name
                tag = ""
                if name.startswith(self._DOUBT_PREFIX):
                    name = name[len(self._DOUBT_PREFIX) :]
                    tag = "[cyan]\\[DOUBT][/cyan] "
                else:
                    m = _CYCLE_RE.match(name)
                    if m:
                        name = name[m.end() :]
                        tag = f"[magenta]\\[C{m.group(1)}][/magenta] "
                    else:
                        m = _DECISION_RE.match(name)
                        if m:
                            name = name[m.end() :]
                            tag = f"[green]\\[D{m.group(1)}][/green] "
                name = name.replace("[", "\\[")
                style = "dim" if t.status == "completed" else ""
                name = f"[{style}]{name}[/{style}]" if style else name
                lines.append(f"{marker} {tag}{name}")
            return "\n".join(lines)
        remaining = state.tasks_total - state.tasks_completed
        return f"completed {state.tasks_completed}  remaining {remaining}  total {state.tasks_total}"


class DoubtPanel:
    _severity_colors: dict[str, str] = {
        "critical": "red",
        "high": "orange1",
        "medium": "yellow",
        "low": "cyan",
    }

    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        if not state.doubts:
            return ""
        resolved = sum(1 for d in state.doubts if d.status == "resolved")
        lines: list[str] = [f"[dim]{resolved}/{len(state.doubts)} resolved[/dim]"]
        for d in state.doubts:
            color = self._severity_colors.get(d.severity, "dim")
            desc = d.description.replace("[", "\\[")
            if d.status == "resolved":
                lines.append(f"[green]✓[/green] [{color}][dim]{desc}[/dim][/{color}]")
            else:
                lines.append(f"[{color}]· {desc}[/{color}]")
        return "\n".join(lines)


class DecisionPanel:
    _severity_colors: dict[str, str] = {
        "critical": "red",
        "high": "orange1",
        "medium": "yellow",
        "low": "green",
    }

    @staticmethod
    def _label_for_action(action: str) -> str:
        normalized = action.lower().replace("-", " ").replace("_", " ").strip()
        if normalized in ("auto fix", "autofix", "fix"):
            return "AUTO-FIX"
        if normalized in ("skip", "reject", "auto skip"):
            return "SKIP"
        return action.upper().replace("-", " ")

    def render_state(self, state: PrdState | None) -> str:
        if state is None:
            return ""
        lines: list[str] = []
        for d in state.autonomous_decisions:
            color = self._severity_colors.get(d.severity, "dim")
            label = self._label_for_action(d.action)
            line = f"[{color}]{label}: {d.issue}[/{color}]"
            if d.reason:
                line += f" [dim]{d.reason}[/dim]"
            lines.append(line)
        for d in state.deferred_decisions:
            color = self._severity_colors.get(d.severity, "red")
            line = f"[bold {color}]⚠ PENDING: {d.issue}[/bold {color}]"
            if d.reason:
                line += f" [dim]{d.reason}[/dim]"
            lines.append(line)
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
            resolutions: list[str] = []
            if c.auto_fixed:
                resolutions.append(f"{c.auto_fixed} fix")
            if c.escalated:
                resolutions.append(f"{c.escalated} esc")
            if c.deferred:
                resolutions.append(f"{c.deferred} def")
            if resolutions:
                parts.append(f"[dim]({', '.join(resolutions)})[/dim]")
            lines.append("  ".join(parts))
        return "\n".join(lines)


class SessionListRenderer:
    def render_entry(self, session: SessionState, is_selected: bool) -> str:
        name = session.project_name or session.session_id
        is_done = session.state is not None and session.state.phase == "done"
        is_inactive = session.stopped or is_done

        if session.state is not None:
            phase = session.state.display_phase
        elif session.stopped:
            phase = "STOPPED"
        else:
            phase = ""

        attention = ""
        if session.state is not None and session.state.needs_attention:
            attention = " [red]\u25cf[/red]"

        line = f"{name}  {phase}{attention}"

        if is_inactive:
            line = f"[dim]{line}[/dim]"
        elif is_selected:
            line = f"[bold]{line}[/bold]"

        return line


class FooterBar:
    def render_content(self) -> str:
        return "q quit │ r refresh │ watching dev/local/autopilot/state.json"
