from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.widget import Widget

from dot.tui.patch import Hunk, parse_diff

__all__ = ["DiffView"]


class DiffView(Widget, can_focus=True):
    """Displays an interactive git diff with hunk and line navigation."""

    BINDINGS = [
        Binding("j", "next_hunk", "Next hunk", show=False),
        Binding("k", "prev_hunk", "Prev hunk", show=False),
        Binding("v", "enter_line_select", "Line select", show=False),
        Binding("escape", "exit_line_select", "Exit select", show=False),
        Binding("space", "toggle_line", "Toggle line", show=False),
    ]

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._diff_text: str = ""
        self._hunks: list[Hunk] = []
        self._focused_hunk: int = 0
        self._staged: bool = False
        self._line_select_mode: bool = False
        self._line_cursor: int = 0
        self._selected_lines: set[int] = set()

    def _exit_line_select(self) -> None:
        """Internal helper to exit line-select mode."""
        self._line_select_mode = False
        self._selected_lines = set()
        self._line_cursor = 0

    def update_diff(self, diff_text: str, *, staged: bool = False) -> None:
        """Replace the current diff content."""
        self._diff_text = diff_text
        self._staged = staged
        self._hunks = parse_diff(diff_text)
        self._focused_hunk = 0
        self._exit_line_select()
        self.refresh()

    @property
    def focused_hunk(self) -> Hunk | None:
        """Currently focused hunk, or None if no hunks."""
        if not self._hunks:
            return None
        return self._hunks[self._focused_hunk]

    @property
    def is_staged(self) -> bool:
        """Whether the current diff is a staged view."""
        return self._staged

    @property
    def hunk_count(self) -> int:
        """Number of hunks in the current diff."""
        return len(self._hunks)

    @property
    def focused_hunk_index(self) -> int:
        """0-based index of the focused hunk."""
        return self._focused_hunk

    @property
    def in_line_select_mode(self) -> bool:
        """Whether line-select mode is active."""
        return self._line_select_mode

    @property
    def selected_line_indices(self) -> set[int]:
        """Indices into focused hunk.lines that are selected."""
        return set(self._selected_lines)

    @property
    def line_cursor(self) -> int:
        """Current line cursor position (index into hunk.lines)."""
        return self._line_cursor

    def _changed_line_indices(self) -> list[int]:
        """Return indices of changed lines (+/-) in the focused hunk."""
        hunk = self.focused_hunk
        if hunk is None:
            return []
        return [i for i, line in enumerate(hunk.lines) if line.startswith("+") or line.startswith("-")]

    def action_next_hunk(self) -> None:
        """Move focus to the next hunk, or next line in line-select mode."""
        if self._line_select_mode:
            self.action_line_down()
            return
        if self._hunks and self._focused_hunk < len(self._hunks) - 1:
            self._focused_hunk += 1
            self.refresh()

    def action_prev_hunk(self) -> None:
        """Move focus to the previous hunk, or previous line in line-select mode."""
        if self._line_select_mode:
            self.action_line_up()
            return
        if self._focused_hunk > 0:
            self._focused_hunk -= 1
            self.refresh()

    def action_enter_line_select(self) -> None:
        """Enter line-select mode on the focused hunk."""
        if self.focused_hunk is None:
            return
        changed = self._changed_line_indices()
        if not changed:
            return
        self._line_select_mode = True
        self._line_cursor = changed[0]
        self._selected_lines = set()
        self.refresh()

    def action_exit_line_select(self) -> None:
        """Exit line-select mode and clear selections."""
        self._exit_line_select()
        self.refresh()

    def action_line_down(self) -> None:
        """Move cursor to the next changed line."""
        if not self._line_select_mode:
            return
        changed = self._changed_line_indices()
        for idx in changed:
            if idx > self._line_cursor:
                self._line_cursor = idx
                self.refresh()
                return

    def action_line_up(self) -> None:
        """Move cursor to the previous changed line."""
        if not self._line_select_mode:
            return
        changed = self._changed_line_indices()
        for idx in reversed(changed):
            if idx < self._line_cursor:
                self._line_cursor = idx
                self.refresh()
                return

    def action_toggle_line(self) -> None:
        """Toggle selection on the current line."""
        if not self._line_select_mode:
            return
        if self._line_cursor in self._selected_lines:
            self._selected_lines.discard(self._line_cursor)
        else:
            self._selected_lines.add(self._line_cursor)
        self.refresh()

    def render(self) -> Text:
        output = Text()

        if not self._diff_text:
            output.append("(no diff)")
            return output

        if "Binary files" in self._diff_text:
            output.append("(binary file)")
            return output

        if not self._hunks:
            # Diff text with no parseable hunks - render raw with styling
            for i, line in enumerate(self._diff_text.split("\n")):
                if i > 0:
                    output.append("\n")
                if line.startswith("---") or line.startswith("+++"):
                    output.append(line, style="bold")
                elif line.startswith("@@"):
                    output.append(line, style="dim")
                elif line.startswith("+"):
                    output.append(line, style="green")
                elif line.startswith("-"):
                    output.append(line, style="red")
                else:
                    output.append(line)
            return output

        # Render file headers (lines before first hunk)
        lines = self._diff_text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("@@"):
                break
            if i > 0:
                output.append("\n")
            if line.startswith("---") or line.startswith("+++"):
                output.append(line, style="bold")
            else:
                output.append(line)

        # Render each hunk
        for hunk_idx, hunk in enumerate(self._hunks):
            is_focused = hunk_idx == self._focused_hunk
            prefix = "> " if is_focused else "  "

            output.append("\n")
            output.append(prefix)
            output.append(hunk.header, style="bold dim" if is_focused else "dim")

            for line_idx, line in enumerate(hunk.lines):
                output.append("\n")
                line_prefix = prefix

                if is_focused and self._line_select_mode:
                    if line_idx == self._line_cursor:
                        line_prefix = "@ "
                    elif line_idx in self._selected_lines:
                        line_prefix = "* "

                output.append(line_prefix)
                if line.startswith("+"):
                    output.append(line, style="green")
                elif line.startswith("-"):
                    output.append(line, style="red")
                else:
                    output.append(line)

        return output
