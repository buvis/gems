from __future__ import annotations

from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget

from dot.tui.commands.browse import DirEntry, TrackingStatus

__all__ = ["DirListWidget"]

_STATUS_COLORS: dict[TrackingStatus, str] = {
    TrackingStatus.TRACKED: "green",
    TrackingStatus.UNTRACKED: "yellow",
    TrackingStatus.IGNORED: "dim",
}


class DirListWidget(Widget, can_focus=True):
    """Displays a list of directory entries with tracking status."""

    cursor_index: reactive[int] = reactive(0)

    class DirEntrySelected(Message):
        """Posted when the cursor moves to a new entry."""

        def __init__(self, entry: DirEntry) -> None:
            super().__init__()
            self.entry = entry

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._entries: list[DirEntry] = []

    def update_entries(self, entries: list[DirEntry]) -> None:
        """Replace the entry list and reset cursor."""
        self._entries = list(entries)
        self.cursor_index = 0
        self.refresh()

    def watch_cursor_index(self, value: int) -> None:
        """Post DirEntrySelected when cursor changes and entries exist."""
        if self._entries:
            self.post_message(self.DirEntrySelected(self._entries[value]))

    def render(self) -> Text:
        output = Text()

        if not self._entries:
            output.append("Empty directory", style="dim")
            return output

        for idx, entry in enumerate(self._entries):
            prefix = "▸ " if idx == self.cursor_index else "  "
            style = "reverse" if idx == self.cursor_index else ""
            color = _STATUS_COLORS.get(entry.status, "white")

            display_name = f"{entry.name}/" if entry.is_dir and entry.name != ".." else entry.name

            output.append(prefix)
            output.append(display_name, style=f"{color} {style}".strip())
            output.append("\n")

        return output

    def action_cursor_down(self) -> None:
        if not self._entries:
            return
        self.cursor_index = (self.cursor_index + 1) % len(self._entries)

    def action_cursor_up(self) -> None:
        if not self._entries:
            return
        self.cursor_index = (self.cursor_index - 1) % len(self._entries)

    @property
    def selected_entry(self) -> DirEntry | None:
        """Return the currently focused DirEntry, or None if empty."""
        if not self._entries:
            return None
        return self._entries[self.cursor_index]

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]
