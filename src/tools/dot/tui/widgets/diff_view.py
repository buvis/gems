from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.widget import Widget

from dot.tui.patch import Hunk, parse_diff

__all__ = ["DiffView"]


class DiffView(Widget, can_focus=True):
    """Displays an interactive git diff with hunk navigation."""

    BINDINGS = [
        Binding("j", "next_hunk", "Next hunk", show=False),
        Binding("k", "prev_hunk", "Prev hunk", show=False),
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

    def update_diff(self, diff_text: str, *, staged: bool = False) -> None:
        """Replace the current diff content."""
        self._diff_text = diff_text
        self._staged = staged
        self._hunks = parse_diff(diff_text)
        self._focused_hunk = 0
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

    def action_next_hunk(self) -> None:
        """Move focus to the next hunk."""
        if self._hunks and self._focused_hunk < len(self._hunks) - 1:
            self._focused_hunk += 1
            self.refresh()

    def action_prev_hunk(self) -> None:
        """Move focus to the previous hunk."""
        if self._focused_hunk > 0:
            self._focused_hunk -= 1
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

            for line in hunk.lines:
                output.append("\n")
                output.append(prefix)
                if line.startswith("+"):
                    output.append(line, style="green")
                elif line.startswith("-"):
                    output.append(line, style="red")
                else:
                    output.append(line)

        return output
