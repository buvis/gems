from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Static

from pidash.tui.state import PrdState, SessionState, parse_session_file, parse_state
from pidash.tui.watcher import (
    SESSIONS_DIR,
    STATE_DIR,
    STATE_FILENAME,
    SessionRemoved,
    SessionUpdated,
    StateChanged,
    StateFileDeleted,
    watch_sessions_dir,
    watch_state_file,
)
from pidash.tui.widgets import (
    DecisionPanel,
    DoubtPanel,
    FooterBar,
    PhasePipeline,
    SessionListRenderer,
    TaskPanel,
)

_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_STALE_SECONDS = 300  # 5 minutes


class _PipelineWidget(Static):
    def __init__(self) -> None:
        super().__init__(id="pipeline")
        self._renderer = PhasePipeline()
        self._state: PrdState | None = None
        self._spin_idx = 0

    def on_mount(self) -> None:
        self.refresh_state(None)
        self.set_interval(0.15, self._tick)

    def _tick(self) -> None:
        if self._state is not None and self._state.phase != "done":
            if self._state.needs_attention:
                return  # stop spinner when waiting for user
            self._spin_idx = (self._spin_idx + 1) % len(_SPINNER)
            self._renderer.spinner = _SPINNER[self._spin_idx]
            self.update(self._renderer.render_state(self._state))

    def refresh_state(self, state: PrdState | None) -> None:
        self._state = state
        self.update(self._renderer.render_state(state))


class _AttentionOverlay(Static):
    def __init__(self) -> None:
        super().__init__(id="attention")

    def on_mount(self) -> None:
        self.display = False

    def show(self) -> None:
        self.display = True
        self.update("[bold white on red]  NEEDS YOUR ATTENTION  [/bold white on red]")

    def hide(self) -> None:
        self.display = False
        self.update("")

    def refresh_state(self, state: PrdState | None) -> None:
        if state is not None and state.needs_attention:
            self.show()
        else:
            self.hide()


class _PanelWidget(Static):
    def __init__(self, panel_id: str, title: str, renderer: TaskPanel | DecisionPanel | DoubtPanel) -> None:
        super().__init__(id=panel_id)
        self._title = title
        self._renderer = renderer

    def on_mount(self) -> None:
        self.refresh_state(None)

    def refresh_state(self, state: PrdState | None) -> None:
        content = self._renderer.render_state(state)
        if content:
            self.update(f"[bold]{self._title}[/bold]\n{content}")
        else:
            self.update("")


class _TaskPanelWidget(_PanelWidget):
    def __init__(self) -> None:
        self._task_renderer = TaskPanel()
        super().__init__("tasks", "Tasks", self._task_renderer)
        self._state: PrdState | None = None
        self._spin_idx = 0

    def on_mount(self) -> None:
        super().on_mount()
        self.set_interval(0.15, self._tick)

    def _tick(self) -> None:
        if self._state is None:
            return
        has_active = any(t.status == "in_progress" for t in self._state.tasks)
        if not has_active:
            return
        self._spin_idx = (self._spin_idx + 1) % len(_SPINNER)
        self._task_renderer.spinner = _SPINNER[self._spin_idx]
        content = self._task_renderer.render_state(self._state)
        if content:
            self.update(f"[bold]{self._title}[/bold]\n{content}")

    def refresh_state(self, state: PrdState | None) -> None:
        self._state = state
        super().refresh_state(state)


class _DoubtPanelWidget(_PanelWidget):
    def __init__(self) -> None:
        super().__init__("doubts", "Doubts", DoubtPanel())

    def on_mount(self) -> None:
        self.display = False
        super().on_mount()

    def refresh_state(self, state: PrdState | None) -> None:
        self.display = state is not None and len(state.doubts) > 0
        super().refresh_state(state)


class _SidebarWidget(Static):
    def __init__(self) -> None:
        super().__init__(id="sidebar")
        self._renderer = SessionListRenderer()

    def refresh_sessions(
        self,
        sessions: dict[str, SessionState],
        active_id: str | None,
        stale_ids: set[str],
    ) -> None:
        if not sessions:
            self.update("[dim]no active sessions[/dim]")
            return
        sorted_sessions = _sort_sessions(sessions)
        lines: list[str] = []
        for s in sorted_sessions:
            is_selected = s.session_id == active_id
            line = self._renderer.render_entry(s, is_selected)
            if s.session_id in stale_ids and not s.stopped:
                line = f"[dim]{line}[/dim]"
            lines.append(line)
        self.update("\n".join(lines))


def _sort_sessions(sessions: dict[str, SessionState]) -> list[SessionState]:
    """Sort: attention first, then active, then done/stopped."""

    def key(s: SessionState) -> tuple[int, str]:
        has_attention = s.state is not None and s.state.needs_attention
        is_done = s.stopped or (s.state is not None and s.state.phase == "done")
        if has_attention:
            rank = 0
        elif is_done:
            rank = 2
        else:
            rank = 1
        return (rank, s.project_name.lower())

    return sorted(sessions.values(), key=key)


class _FooterWidget(Static):
    def __init__(self, multi_session: bool = False) -> None:
        super().__init__(id="footer")
        self._renderer = FooterBar()
        self._multi_session = multi_session
        self._session_count = 0

    def on_mount(self) -> None:
        self._update_content()

    def refresh_state(self, state: PrdState | None) -> None:
        pass

    def set_session_count(self, count: int) -> None:
        self._session_count = count
        self._update_content()

    def _update_content(self) -> None:
        if self._multi_session:
            self.update(
                f"q quit \u2502 r refresh \u2502 \u2191/\u2193 switch session \u2502 {self._session_count} sessions"
            )
        else:
            self.update(self._renderer.render_content())


class PidashApp(App[None]):
    TITLE = "pidash"
    CSS = """
#pipeline { dock: top; height: auto; padding: 0 1; }
#attention { dock: top; height: 5; content-align: center middle; padding: 1; }
#main-container { height: 1fr; }
#sidebar { width: 25; padding: 1; border-right: solid $surface-lighten-2; }
#detail { width: 1fr; }
#panels { height: 1fr; }
#panels > Static { width: 1fr; padding: 1; border: solid $surface-lighten-2; }
#footer { dock: bottom; height: 1; background: $surface; color: $text-muted; padding: 0 1; }
.attention-mode { background: #3a1a1a; }
.attention-mode #panels > Static { border: solid red; }
"""
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("up", "prev_session", "Prev session", show=False),
        Binding("down", "next_session", "Next session", show=False),
    ]

    def __init__(self, project_path: Path | None = None, *, _watch: bool = True) -> None:
        super().__init__()
        self._project_path = project_path
        self._state: PrdState | None = None
        self._watch = _watch
        self._stop_event = threading.Event()
        # Multi-session state
        self._sessions: dict[str, SessionState] = {}
        self._active_session_id: str | None = None
        self._stale_ids: set[str] = set()

    @property
    def _is_multi_session(self) -> bool:
        return self._project_path is None

    def compose(self) -> ComposeResult:
        if self._is_multi_session:
            yield _PipelineWidget()
            yield _AttentionOverlay()
            with Horizontal(id="main-container"):
                yield _SidebarWidget()
                with Vertical(id="detail"):
                    with Horizontal(id="panels"):
                        yield _TaskPanelWidget()
                        yield _PanelWidget("decisions", "Decisions", DecisionPanel())
                        yield _DoubtPanelWidget()
            yield _FooterWidget(multi_session=True)
        else:
            yield _PipelineWidget()
            yield _AttentionOverlay()
            with Horizontal(id="panels"):
                yield _TaskPanelWidget()
                yield _PanelWidget("decisions", "Decisions", DecisionPanel())
                yield _DoubtPanelWidget()
            yield _FooterWidget()

    def on_mount(self) -> None:
        if self._is_multi_session:
            self._refresh_all()
            if self._watch:
                stop = self._stop_event
                self.run_worker(
                    lambda: watch_sessions_dir(self, stop),
                    name="session-watcher",
                    thread=True,
                    exclusive=True,
                )
            self.set_interval(30, self._check_stale)
        else:
            self._refresh_all()
            if self._watch:
                stop = self._stop_event
                self.run_worker(
                    lambda: watch_state_file(self, self._project_path, stop_event=stop),  # type: ignore[arg-type]
                    name="state-watcher",
                    thread=True,
                    exclusive=True,
                )

    def on_unmount(self) -> None:
        self._stop_event.set()

    # --- Single-project handlers ---

    def on_state_changed(self, message: StateChanged) -> None:
        parsed = parse_state(message.raw)
        if parsed is not None:
            self._state = parsed
            self._refresh_all()

    def on_state_file_deleted(self, _message: StateFileDeleted) -> None:
        self._state = None
        self._refresh_all()

    # --- Multi-session handlers ---

    def on_session_updated(self, message: SessionUpdated) -> None:
        session = parse_session_file(message.raw)
        if session is None:
            return
        self._sessions[message.session_id] = session
        if self._active_session_id is None:
            self._active_session_id = message.session_id
        self._refresh_multi()

    def on_session_removed(self, message: SessionRemoved) -> None:
        self._sessions.pop(message.session_id, None)
        if self._active_session_id == message.session_id:
            self._active_session_id = next(iter(self._sessions), None)
        self._refresh_multi()

    # --- Actions ---

    def action_refresh(self) -> None:
        if self._is_multi_session:
            self._reload_sessions()
        else:
            state_file = self._project_path / STATE_DIR / STATE_FILENAME  # type: ignore[operator]
            try:
                raw = state_file.read_text(encoding="utf-8")
                parsed = parse_state(raw)
                if parsed is not None:
                    self._state = parsed
            except OSError:
                self._state = None
            self._refresh_all()

    def action_prev_session(self) -> None:
        if not self._is_multi_session or not self._sessions:
            return
        self._switch_session(-1)

    def action_next_session(self) -> None:
        if not self._is_multi_session or not self._sessions:
            return
        self._switch_session(1)

    # --- Internal ---

    def _switch_session(self, direction: int) -> None:
        sorted_sessions = _sort_sessions(self._sessions)
        if not sorted_sessions:
            return
        ids = [s.session_id for s in sorted_sessions]
        if self._active_session_id in ids:
            idx = ids.index(self._active_session_id)
            idx = (idx + direction) % len(ids)
        else:
            idx = 0
        self._active_session_id = ids[idx]
        self._refresh_multi()

    def _reload_sessions(self) -> None:
        self._sessions.clear()
        if SESSIONS_DIR.is_dir():
            for f in sorted(SESSIONS_DIR.glob("*.json")):
                try:
                    raw = f.read_text(encoding="utf-8")
                    session = parse_session_file(raw)
                    if session is not None:
                        self._sessions[session.session_id] = session
                except OSError:
                    pass
        if self._active_session_id not in self._sessions:
            self._active_session_id = next(iter(self._sessions), None)
        self._refresh_multi()

    def _check_stale(self) -> None:
        now = datetime.now(timezone.utc)
        stale: set[str] = set()
        for sid, session in self._sessions.items():
            if session.updated_at is None:
                continue
            if session.stopped or (session.state is not None and session.state.phase == "done"):
                continue
            updated = session.updated_at
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            age = (now - updated).total_seconds()
            if age > _STALE_SECONDS:
                stale.add(sid)
        if stale != self._stale_ids:
            self._stale_ids = stale
            self._refresh_sidebar()

    def _refresh_multi(self) -> None:
        active = self._sessions.get(self._active_session_id) if self._active_session_id else None
        self._state = active.state if active else None
        self._refresh_all()
        self._refresh_sidebar()
        footer = self.query_one("#footer", _FooterWidget)
        footer.set_session_count(len(self._sessions))

    def _refresh_sidebar(self) -> None:
        try:
            sidebar = self.query_one("#sidebar", _SidebarWidget)
            sidebar.refresh_sessions(self._sessions, self._active_session_id, self._stale_ids)
        except NoMatches:
            pass

    def _refresh_all(self) -> None:
        attention = self._state is not None and self._state.needs_attention
        if attention:
            self.add_class("attention-mode")
        else:
            self.remove_class("attention-mode")
        for widget in self.query(Static):
            if hasattr(widget, "refresh_state"):
                widget.refresh_state(self._state)
