from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from dot.tui.models import BranchInfo

__all__ = ["StatusBar"]


class StatusBar(Static):
    """Header bar showing branch name, ahead/behind, and secret count."""

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._info: BranchInfo | None = None

    def update_info(self, info: BranchInfo) -> None:
        self._info = info
        self.update(self._render_info())

    def _render_info(self) -> Text:
        if self._info is None:
            return Text("(no branch info)", style="dim")

        output = Text()
        output.append(self._info.name, style="bold cyan")

        if self._info.ahead > 0:
            output.append(f"  \u2191{self._info.ahead} ahead", style="yellow")

        if self._info.behind > 0:
            output.append(f"  \u2193{self._info.behind} behind", style="red")

        if self._info.secret_count > 0:
            output.append(f"  \U0001f512{self._info.secret_count} secrets", style="magenta")

        return output
