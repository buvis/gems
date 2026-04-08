from __future__ import annotations

from rich.text import Text
from textual.geometry import Region
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from dot.tui.models import FileEntry

__all__ = ["FileListWidget"]

_STATUS_COLORS: dict[str, str] = {
    "M": "yellow",
    "A": "green",
    "D": "red",
    "?": "dim",
}


class FileListWidget(Widget, can_focus=True):
    """Displays a list of files with git status indicators."""

    cursor_index: reactive[int] = reactive(0)

    class FileSelected(Message):
        """Posted when the cursor moves to a new file."""

        def __init__(self, entry: FileEntry, staged: bool) -> None:
            super().__init__()
            self.entry = entry
            self.staged = staged

    def __init__(
        self,
        title: str,
        *,
        staged: bool = False,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._title = title
        self._staged = staged
        self._files: list[FileEntry] = []

    def update_files(self, files: list[FileEntry]) -> None:
        """Replace the file list and reset cursor."""
        self._files = list(files)
        old_cursor = self.cursor_index
        self.cursor_index = 0
        self.refresh()
        # If cursor didn't change, watch_cursor_index didn't fire — post explicitly
        if old_cursor == 0 and self._files and self.has_focus:
            self.post_message(self.FileSelected(self._files[0], self._staged))

    def watch_cursor_index(self, value: int) -> None:
        """Post FileSelected when cursor changes and widget is focused."""
        if self._files:
            if self.has_focus:
                self.post_message(self.FileSelected(self._files[value], self._staged))
            # Title is line 0, files start at line 1
            self.scroll_to_region(Region(0, value + 1, 1, 1), animate=False)

    def on_focus(self) -> None:
        """Refresh diff when this pane gains focus."""
        if self._files:
            self.post_message(self.FileSelected(self._files[self.cursor_index], self._staged))

    def render(self) -> Text:
        output = Text()
        output.append(self._title, style="bold underline")
        output.append("\n")

        if not self._files:
            output.append("  No changes", style="dim")
            return output

        for idx, entry in enumerate(self._files):
            is_selected = idx == self.cursor_index and self.has_focus
            prefix = "▸ " if is_selected else "  "
            style = "reverse" if is_selected else ""

            status_char = entry.status.strip() or "?"
            color = _STATUS_COLORS.get(status_char[0], "white")

            output.append(prefix)
            output.append(f"[{entry.status.strip():>2}] ", style=color)
            output.append(entry.path, style=style)

            if entry.is_secret:
                output.append(" [secret]", style="magenta bold")

            output.append("\n")

        return output

    def action_cursor_down(self) -> None:
        if not self._files:
            return
        self.cursor_index = (self.cursor_index + 1) % len(self._files)

    def action_cursor_up(self) -> None:
        if not self._files:
            return
        self.cursor_index = (self.cursor_index - 1) % len(self._files)

    @property
    def is_empty(self) -> bool:
        """Return True if the file list has no entries."""
        return not self._files

    @property
    def selected_entry(self) -> FileEntry | None:
        """Return the currently focused FileEntry, or None if empty."""
        if not self._files:
            return None
        return self._files[self.cursor_index]

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("down", "cursor_down", "Down"),
        ("up", "cursor_up", "Up"),
    ]
