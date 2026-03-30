from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

__all__ = ["DiffView"]


class DiffView(Widget, can_focus=True):
    """Displays a styled git diff."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._diff_text: str = ""

    def update_diff(self, diff_text: str) -> None:
        """Replace the current diff content."""
        self._diff_text = diff_text

    def render(self) -> Text:
        output = Text()

        if not self._diff_text:
            output.append("(no diff)")
            return output

        if "Binary files" in self._diff_text:
            output.append("(binary file)")
            return output

        lines = self._diff_text.split("\n")
        for i, line in enumerate(lines):
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
