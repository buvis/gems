from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.binding import Binding
from textual.geometry import Region
from textual.widget import Widget

from dot.tui.patch import Hunk, parse_diff

__all__ = ["DiffView"]


@dataclass(frozen=True)
class _DiffScrollState:
    focused_hunk: int
    line_select_mode: bool
    line_cursor: int
    selected_lines: frozenset[int]


class DiffView(Widget, can_focus=True):
    """Displays an interactive git diff with hunk and line navigation."""

    BINDINGS = [
        Binding("j", "next_hunk", "Next hunk", show=False),
        Binding("k", "prev_hunk", "Prev hunk", show=False),
        Binding("down", "next_hunk", "Next hunk", show=False),
        Binding("up", "prev_hunk", "Prev hunk", show=False),
        Binding("v", "enter_line_select", "Line select", show=False),
        Binding("escape", "exit_line_select", "Exit select", show=False),
        Binding("ctrl+d", "page_down", "Half page down", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("ctrl+u", "page_up", "Half page up", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
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
        self._current_path: str = ""
        self._scroll_state: dict[str, _DiffScrollState] = {}

    def _exit_line_select(self) -> None:
        """Internal helper to exit line-select mode."""
        self._line_select_mode = False
        self._selected_lines = set()
        self._line_cursor = 0

    def _save_scroll_state(self) -> None:
        """Save current scroll state for the current path."""
        if self._current_path and self._hunks:
            self._scroll_state[self._current_path] = _DiffScrollState(
                focused_hunk=self._focused_hunk,
                line_select_mode=self._line_select_mode,
                line_cursor=self._line_cursor,
                selected_lines=frozenset(self._selected_lines),
            )

    def _restore_scroll_state(self, path: str) -> None:
        """Restore saved scroll state for a path if available."""
        state = self._scroll_state.get(path)
        if state is None:
            return
        if state.focused_hunk < len(self._hunks):
            self._focused_hunk = state.focused_hunk
            hunk = self._hunks[self._focused_hunk]
            max_line = len(hunk.lines) - 1 if hunk.lines else 0
            self._line_cursor = min(state.line_cursor, max_line)
            self._selected_lines = {i for i in state.selected_lines if i <= max_line}
            self._line_select_mode = state.line_select_mode and bool(hunk.lines)

    def update_diff(self, diff_text: str, *, staged: bool = False, path: str = "") -> None:
        """Replace the current diff content."""
        self._save_scroll_state()
        self._diff_text = diff_text
        self._staged = staged
        self._hunks = parse_diff(diff_text)
        self._focused_hunk = 0
        self._exit_line_select()
        self._current_path = path
        if path:
            self._restore_scroll_state(path)
            self._scroll_to_hunk()
        self.refresh()

    def clear_scroll_state(self, path: str) -> None:
        """Remove saved scroll state for a path (e.g. after staging invalidates hunks).

        Also resets _current_path if it matches, so the next update_diff
        call won't re-save the stale state via _save_scroll_state.
        """
        self._scroll_state.pop(path, None)
        if self._current_path == path:
            self._current_path = ""

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

    def _file_header_line_count(self) -> int:
        """Count rendered lines before the first hunk header."""
        count = 0
        for line in self._diff_text.split("\n"):
            if line.startswith("@@"):
                break
            count += 1
        return count

    def _hunk_line_offset(self, hunk_idx: int) -> int:
        """Compute the rendered line offset of the given hunk header."""
        offset = self._file_header_line_count()
        for i in range(hunk_idx):
            offset += 1 + len(self._hunks[i].lines)  # header + content lines
        return offset

    def _scroll_to_hunk(self) -> None:
        """Scroll to keep the focused hunk visible.

        For the last hunk in a multi-hunk diff, target the bottom of its
        content so long final hunks are reachable by keyboard alone.
        Single-hunk diffs always target the header so opening a file
        lands at the top of its diff, not the bottom.
        """
        if not self._hunks:
            return
        line = self._hunk_line_offset(self._focused_hunk)
        if self._focused_hunk > 0 and self._focused_hunk == len(self._hunks) - 1:
            line += len(self._hunks[self._focused_hunk].lines)
        self.scroll_to_region(Region(0, line, 1, 1), animate=False)

    def _scroll_to_line(self) -> None:
        """Scroll to keep the current line cursor visible."""
        if not self._hunks:
            return
        line = self._hunk_line_offset(self._focused_hunk) + 1 + self._line_cursor
        self.scroll_to_region(Region(0, line, 1, 1), animate=False)

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
            self._scroll_to_hunk()
            self.refresh()

    def action_prev_hunk(self) -> None:
        """Move focus to the previous hunk, or previous line in line-select mode."""
        if self._line_select_mode:
            self.action_line_up()
            return
        if self._focused_hunk > 0:
            self._focused_hunk -= 1
            self._scroll_to_hunk()
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
                self._scroll_to_line()
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
                self._scroll_to_line()
                self.refresh()
                return

    def action_page_down(self) -> None:
        """Scroll down by half the viewport height regardless of focus."""
        delta = max(1, self.size.height // 2)
        self.scroll_relative(y=delta, animate=False)

    def action_page_up(self) -> None:
        """Scroll up by half the viewport height regardless of focus."""
        delta = max(1, self.size.height // 2)
        self.scroll_relative(y=-delta, animate=False)

    def action_scroll_top(self) -> None:
        """Scroll to the top of the diff."""
        self.scroll_home(animate=False)

    def action_scroll_bottom(self) -> None:
        """Scroll to the bottom of the diff."""
        self.scroll_end(animate=False)

    def action_toggle_line(self) -> None:
        """Toggle selection on the current line."""
        if not self._line_select_mode:
            return
        if self._line_cursor in self._selected_lines:
            self._selected_lines.discard(self._line_cursor)
        else:
            self._selected_lines.add(self._line_cursor)
        self.refresh()

    def _render_raw_diff(self, output: Text) -> None:
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

    def _line_prefix(self, is_focused: bool, prefix: str, line_idx: int) -> str:
        if is_focused and self._line_select_mode:
            if line_idx == self._line_cursor:
                return "@ "
            if line_idx in self._selected_lines:
                return "* "
        return prefix

    def _render_hunks(self, output: Text) -> None:
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

        for hunk_idx, hunk in enumerate(self._hunks):
            is_focused = hunk_idx == self._focused_hunk
            prefix = "> " if is_focused else "  "

            if output.plain:
                output.append("\n")
            output.append(prefix)
            output.append(hunk.header, style="bold dim" if is_focused else "dim")

            for line_idx, line in enumerate(hunk.lines):
                output.append("\n")
                output.append(self._line_prefix(is_focused, prefix, line_idx))
                if line.startswith("+"):
                    output.append(line, style="green")
                elif line.startswith("-"):
                    output.append(line, style="red")
                else:
                    output.append(line)

    def render(self) -> Text:
        output = Text()

        if not self._diff_text:
            output.append("(no diff)")
            return output

        if "Binary files" in self._diff_text:
            output.append("(binary file)")
            return output

        if not self._hunks:
            self._render_raw_diff(output)
        else:
            self._render_hunks(output)

        return output
