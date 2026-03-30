from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Label

from dot.tui.commands.browse import TrackingStatus, list_directory
from dot.tui.widgets.dir_list import DirListWidget
from dot.tui.widgets.gitignore_modal import GitignoreModal

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from dot.tui.git_ops import GitOps

__all__ = ["BrowseScreen"]


class BrowseScreen(Screen):
    """Browse dotfiles directory tree with tracking status."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Back"),
        Binding("a", "stage_entry", "Stage"),
        Binding("i", "ignore_entry", "Ignore"),
        Binding("e", "encrypt_entry", "Encrypt"),
        Binding("enter", "open_entry", "Open", show=False),
        Binding("backspace", "go_parent", "Parent", show=False),
    ]

    def __init__(self, git_ops: GitOps) -> None:
        super().__init__()
        self._git_ops = git_ops
        self._current_path = git_ops.dotfiles_root

    def compose(self) -> ComposeResult:
        yield Label(self._current_path, id="browse-path")
        yield DirListWidget(id="dir-list")

    def on_mount(self) -> None:
        self._refresh_listing()
        self.query_one("#dir-list", DirListWidget).focus()

    def _refresh_listing(self) -> None:
        entries = list_directory(self._git_ops, self._current_path)
        self.query_one("#dir-list", DirListWidget).update_entries(entries)
        self.query_one("#browse-path", Label).update(self._current_path)

    def _navigate_to(self, path: str) -> None:
        self._current_path = path
        self._refresh_listing()

    def action_dismiss_screen(self) -> None:
        self.dismiss()

    def action_open_entry(self) -> None:
        widget = self.query_one("#dir-list", DirListWidget)
        entry = widget.selected_entry
        if entry is None:
            return
        if entry.is_dir:
            self._navigate_to(entry.path)

    def action_go_parent(self) -> None:
        parent = str(Path(self._current_path).parent)
        self._navigate_to(parent)

    def action_stage_entry(self) -> None:
        widget = self.query_one("#dir-list", DirListWidget)
        entry = widget.selected_entry
        if entry is None:
            return
        if entry.status != TrackingStatus.UNTRACKED:
            return
        self._git_ops.stage(entry.path)
        self._refresh_listing()

    def action_encrypt_entry(self) -> None:
        from dot.tui.commands.secrets import register_secret

        widget = self.query_one("#dir-list", DirListWidget)
        entry = widget.selected_entry
        if entry is None:
            return
        if not self._git_ops.shell.is_command_available("git-secret"):
            return
        register_secret(self._git_ops, entry.path)
        self._refresh_listing()

    def action_ignore_entry(self) -> None:
        widget = self.query_one("#dir-list", DirListWidget)
        entry = widget.selected_entry
        if entry is None:
            return

        def _on_dismiss(pattern: str | None) -> None:
            if pattern is None:
                return
            self._git_ops.add_to_gitignore(pattern)
            self._refresh_listing()

        self.app.push_screen(GitignoreModal(entry.path), callback=_on_dismiss)
