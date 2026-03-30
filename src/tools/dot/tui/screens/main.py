from __future__ import annotations

from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

from dot.tui.widgets import FileListWidget, StatusBar

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from dot.tui.git_ops import GitOps
    from dot.tui.models import FileEntry

__all__ = ["MainScreen"]


class _DiffPane(Static, can_focus=True):
    """Focusable diff viewer."""


class MainScreen(Screen):
    """Two-pane dotfiles status screen."""

    CSS = """
    StatusBar { dock: top; height: 1; background: $surface; padding: 0 1; }
    #main { height: 1fr; }
    #left { width: 40%; }
    #right { width: 60%; }
    #unstaged { height: 1fr; border: solid $surface-lighten-2; padding: 1; }
    #staged { height: 1fr; border: solid $surface-lighten-2; padding: 1; }
    #diff { height: 1fr; border: solid $surface-lighten-2; padding: 1; overflow-y: auto; }
    #unstaged:focus { border: solid $accent; }
    #staged:focus { border: solid $accent; }
    #diff:focus { border: solid $accent; }
    """

    BINDINGS = [
        Binding("tab", "focus_next_pane", "Next pane", show=False),
        Binding("s", "stage_file", "Stage", show=True),
        Binding("u", "unstage_file", "Unstage", show=True),
    ]

    _FOCUS_ORDER = ["unstaged", "staged", "diff"]

    def __init__(self, git_ops: GitOps) -> None:
        super().__init__()
        self._git_ops = git_ops

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield FileListWidget("Unstaged", staged=False, id="unstaged")
                yield FileListWidget("Staged", staged=True, id="staged")
            yield _DiffPane("", id="diff")

    def on_mount(self) -> None:
        self.refresh_status()
        self.query_one("#unstaged", FileListWidget).focus()

    def on_file_list_widget_file_selected(
        self, message: FileListWidget.FileSelected
    ) -> None:
        diff_text = self._git_ops.diff(message.entry.path, staged=message.staged)
        self.query_one("#diff", _DiffPane).update(diff_text or "(no diff)")

    def refresh_status(self) -> None:
        entries = self._git_ops.status()
        staged: list[FileEntry] = []
        unstaged: list[FileEntry] = []

        for entry in entries:
            x_char = entry.status[0]
            y_char = entry.status[1]

            if entry.status == "??":
                unstaged.append(entry)
            else:
                if x_char != " " and x_char != "?":
                    staged.append(entry)
                if y_char != " ":
                    unstaged.append(entry)

        self.query_one("#unstaged", FileListWidget).update_files(unstaged)
        self.query_one("#staged", FileListWidget).update_files(staged)
        self.query_one("#status-bar", StatusBar).update_info(
            self._git_ops.branch_info()
        )

    def action_focus_next_pane(self) -> None:
        focused = self.focused
        current_id = focused.id if focused else ""

        try:
            idx = self._FOCUS_ORDER.index(current_id)
            next_idx = (idx + 1) % len(self._FOCUS_ORDER)
        except ValueError:
            next_idx = 0

        self.query_one(f"#{self._FOCUS_ORDER[next_idx]}").focus()

    def action_stage_file(self) -> None:
        widget = self.query_one("#unstaged", FileListWidget)
        entry = widget.selected_entry
        if entry is None:
            return
        result = self._git_ops.stage(entry.path)
        if not result.success:
            self.query_one("#diff", _DiffPane).update(f"Error staging: {result.error}")
            return
        self.refresh_status()

    def action_unstage_file(self) -> None:
        widget = self.query_one("#staged", FileListWidget)
        entry = widget.selected_entry
        if entry is None:
            return
        result = self._git_ops.unstage(entry.path)
        if not result.success:
            self.query_one("#diff", _DiffPane).update(f"Error unstaging: {result.error}")
            return
        self.refresh_status()
