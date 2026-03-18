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
    CyclePanel,
    DecisionPanel,
    FooterBar,
    HeaderBar,
    PhasePipeline,
    ProgressSection,
    TaskPanel,
)


class _HeaderWidget(Static):
    def __init__(self) -> None:
        super().__init__(id="header")
        self._renderer = HeaderBar()
        self.last_text = ""

    def on_mount(self) -> None:
        self.refresh_state(None)

    def refresh_state(self, state: PrdState | None) -> None:
        self.last_text = self._renderer.render_state(state)
        self.update(self.last_text)


class _PipelineWidget(Static):
    def __init__(self) -> None:
        super().__init__(id="pipeline")
        self._renderer = PhasePipeline()

    def on_mount(self) -> None:
        self.refresh_state(None)

    def refresh_state(self, state: PrdState | None) -> None:
        self.update(self._renderer.render_state(state))


class _ProgressWidget(Static):
    def __init__(self) -> None:
        super().__init__(id="progress")
        self._renderer = ProgressSection()

    def on_mount(self) -> None:
        self.refresh_state(None)

    def refresh_state(self, state: PrdState | None) -> None:
        content = self._renderer.render_state(state)
        self.display = bool(content)
        self.update(content)


class _PanelWidget(Static):
    def __init__(self, panel_id: str, title: str, renderer: TaskPanel | DecisionPanel | CyclePanel) -> None:
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
#header { dock: top; height: 1; background: $primary; color: $text; padding: 0 1; }
#pipeline { dock: top; height: 3; padding: 1 1; }
#progress { dock: top; height: 1; padding: 0 1; }
#panels { height: 1fr; }
#panels > Static { width: 1fr; padding: 1; border: solid $surface-lighten-2; }
#footer { dock: bottom; height: 1; background: $surface; color: $text-muted; padding: 0 1; }
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
        yield _HeaderWidget()
        yield _PipelineWidget()
        yield _ProgressWidget()
        with Horizontal(id="panels"):
            yield _PanelWidget("tasks", "Tasks", TaskPanel())
            yield _PanelWidget("decisions", "Decisions", DecisionPanel())
            yield _PanelWidget("cycles", "Cycles", CyclePanel())
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
        for widget in self.query(Static):
            if hasattr(widget, "refresh_state"):
                widget.refresh_state(self._state)
