from __future__ import annotations

from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer

from dot.tui.patch import build_hunk_patch, build_line_patch
from dot.tui.widgets import CommitModal, DiffView, FileListWidget, GitignoreModal, StatusBar

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from dot.tui.git_ops import GitOps
    from dot.tui.models import FileEntry

__all__ = ["MainScreen"]


class _ConfirmDeleteScreen(ModalScreen[bool]):
    """Yes/no confirmation for file deletion."""

    CSS = """
    _ConfirmDeleteScreen {
        align: center middle;
    }
    #confirm-box {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        from textual.widgets import Label

        with Vertical(id="confirm-box"):
            yield Label(f"Delete '{self._path}'?")
            yield Label("y = yes, n/Esc = cancel", classes="dim")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


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
        Binding("space", "toggle_stage", "Toggle", show=True),
        Binding("d", "delete_file", "Delete", show=True),
        Binding("i", "ignore_file", "Ignore", show=True),
        Binding("c", "commit", "Commit", show=True),
        Binding("p", "push", "Push", show=True),
        Binding("P", "pull", "Pull", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("enter", "stage_hunk", "Stage hunk", show=False),
    ]

    _FOCUS_ORDER = ["unstaged", "staged", "diff"]

    def __init__(self, git_ops: GitOps) -> None:
        super().__init__()
        self._git_ops = git_ops
        self._current_diff_path: str = ""
        self._current_diff_staged: bool = False

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield FileListWidget("Unstaged", staged=False, id="unstaged")
                yield FileListWidget("Staged", staged=True, id="staged")
            yield DiffView(id="diff")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_status()
        self.query_one("#unstaged", FileListWidget).focus()

    def on_file_list_widget_file_selected(
        self, message: FileListWidget.FileSelected
    ) -> None:
        self._current_diff_path = message.entry.path
        self._current_diff_staged = message.staged
        diff_text = self._git_ops.diff(message.entry.path, staged=message.staged)
        self.query_one("#diff", DiffView).update_diff(diff_text or "", staged=message.staged)

    def _show_message(self, msg: str) -> None:
        self.query_one("#diff", DiffView).update_diff(msg)

    def _selected_entry(self) -> FileEntry | None:
        focused = self.focused
        if focused and isinstance(focused, FileListWidget):
            return focused.selected_entry
        return None

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

    def action_toggle_stage(self) -> None:
        focused = self.focused
        if focused and focused.id == "unstaged":
            self.action_stage_file()
        elif focused and focused.id == "staged":
            self.action_unstage_file()

    def action_stage_file(self) -> None:
        widget = self.query_one("#unstaged", FileListWidget)
        entry = widget.selected_entry
        if entry is None:
            return
        result = self._git_ops.stage(entry.path)
        if not result.success:
            self._show_message(f"Error staging: {result.error}")
            return
        self.refresh_status()

    def action_unstage_file(self) -> None:
        widget = self.query_one("#staged", FileListWidget)
        entry = widget.selected_entry
        if entry is None:
            return
        result = self._git_ops.unstage(entry.path)
        if not result.success:
            self._show_message(f"Error unstaging: {result.error}")
            return
        self.refresh_status()

    def action_delete_file(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            result = self._git_ops.rm(entry.path)
            if not result.success:
                self._show_message(f"Error deleting: {result.error}")
                return
            self.refresh_status()

        self.app.push_screen(_ConfirmDeleteScreen(entry.path), callback=_on_confirm)

    def action_ignore_file(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return

        def _on_dismiss(pattern: str | None) -> None:
            if pattern is None:
                return
            result = self._git_ops.add_to_gitignore(pattern)
            if not result.success:
                self._show_message(f"Error adding to .gitignore: {result.error}")
                return
            self.refresh_status()

        self.app.push_screen(GitignoreModal(entry.path), callback=_on_dismiss)

    def action_commit(self) -> None:
        staged_widget = self.query_one("#staged", FileListWidget)
        if staged_widget.is_empty:
            self._show_message("Nothing staged to commit")
            return

        def _on_dismiss(message: str | None) -> None:
            if message is None:
                return
            result = self._git_ops.commit(message)
            if not result.success:
                self._show_message(f"Commit failed: {result.error}")
                return
            self._show_message("Committed successfully")
            self.refresh_status()

        self.app.push_screen(CommitModal(), callback=_on_dismiss)

    def action_push(self) -> None:
        result = self._git_ops.push()
        self._show_message(result.output or result.error or "Push complete")
        self.refresh_status()

    def action_pull(self) -> None:
        result = self._git_ops.pull()
        self._show_message(result.output or result.error or "Pull complete")
        self.refresh_status()

    def action_refresh(self) -> None:
        self.refresh_status()

    def action_stage_hunk(self) -> None:
        focused = self.focused
        if not focused or focused.id != "diff":
            return
        diff_view = self.query_one("#diff", DiffView)
        hunk = diff_view.focused_hunk
        if hunk is None or not self._current_diff_path:
            return
        if diff_view.in_line_select_mode and diff_view.selected_line_indices:
            patch = build_line_patch(
                self._current_diff_path, hunk, diff_view.selected_line_indices
            )
        else:
            patch = build_hunk_patch(self._current_diff_path, hunk)
        if diff_view.is_staged:
            result = self._git_ops.apply_patch_reverse(patch)
        else:
            result = self._git_ops.apply_patch(patch)
        if not result.success:
            self._show_message(f"Error applying patch: {result.error}")
            return
        self.refresh_status()
        diff_text = self._git_ops.diff(
            self._current_diff_path, staged=self._current_diff_staged
        )
        diff_view.update_diff(diff_text or "", staged=self._current_diff_staged)
