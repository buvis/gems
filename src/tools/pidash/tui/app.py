from __future__ import annotations

import threading
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Static

from pidash.tui.state import PrdState, parse_state
from pidash.tui.watcher import STATE_DIR, STATE_FILENAME, StateChanged, StateFileDeleted, watch_state_file
from pidash.tui.widgets import (
    DecisionPanel,
    FooterBar,
    PhasePipeline,
    TaskPanel,
)

_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


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
    def __init__(self, panel_id: str, title: str, renderer: TaskPanel | DecisionPanel) -> None:
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


class _FooterWidget(Static):
    def __init__(self) -> None:
        super().__init__(id="footer")
        self._renderer = FooterBar()

    def on_mount(self) -> None:
        self.update(self._renderer.render_content())

    def refresh_state(self, state: PrdState | None) -> None:
        pass


class PidashApp(App[None]):
    TITLE = "pidash"
    CSS = """
#pipeline { dock: top; height: auto; padding: 0 1; }
#attention { dock: top; height: 5; content-align: center middle; padding: 1; }
#panels { height: 1fr; }
#panels > Static { width: 1fr; padding: 1; border: solid $surface-lighten-2; }
#footer { dock: bottom; height: 1; background: $surface; color: $text-muted; padding: 0 1; }
.attention-mode { background: #3a1a1a; }
.attention-mode #panels > Static { border: solid red; }
"""
    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self, project_path: Path, *, _watch: bool = True) -> None:
        super().__init__()
        self._project_path = project_path
        self._state: PrdState | None = None
        self._watch = _watch
        self._stop_event = threading.Event()

    def compose(self) -> ComposeResult:
        yield _PipelineWidget()
        yield _AttentionOverlay()
        with Horizontal(id="panels"):
            yield _TaskPanelWidget()
            yield _PanelWidget("decisions", "Decisions", DecisionPanel())
        yield _FooterWidget()

    def on_mount(self) -> None:
        self._refresh_all()
        if self._watch:
            stop = self._stop_event
            self.run_worker(
                lambda: watch_state_file(self, self._project_path, stop_event=stop),
                name="state-watcher",
                thread=True,
                exclusive=True,
            )

    def on_unmount(self) -> None:
        self._stop_event.set()

    def on_state_changed(self, message: StateChanged) -> None:
        parsed = parse_state(message.raw)
        if parsed is not None:
            self._state = parsed
            self._refresh_all()

    def on_state_file_deleted(self, _message: StateFileDeleted) -> None:
        self._state = None
        self._refresh_all()

    def action_refresh(self) -> None:
        state_file = self._project_path / STATE_DIR / STATE_FILENAME
        try:
            raw = state_file.read_text(encoding="utf-8")
            parsed = parse_state(raw)
            if parsed is not None:
                self._state = parsed
        except OSError:
            self._state = None
        self._refresh_all()

    def _refresh_all(self) -> None:
        attention = self._state is not None and self._state.needs_attention
        if attention:
            self.add_class("attention-mode")
        else:
            self.remove_class("attention-mode")
        for widget in self.query(Static):
            if hasattr(widget, "refresh_state"):
                widget.refresh_state(self._state)
