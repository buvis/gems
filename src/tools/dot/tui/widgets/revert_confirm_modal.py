from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

__all__ = ["RevertConfirmModal"]


class RevertConfirmModal(ModalScreen[bool]):
    """Confirm a destructive revert of a hunk or selected lines."""

    CSS = """
    RevertConfirmModal {
        align: center middle;
    }
    RevertConfirmModal > Vertical {
        width: auto;
        max-width: 80%;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("enter", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, *, path: str, hunk_header: str, plus_count: int, minus_count: int) -> None:
        super().__init__()
        self._path = path
        self._hunk_header = hunk_header
        self._plus_count = plus_count
        self._minus_count = minus_count

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Revert changes in {self._path}?")
            yield Label(self._hunk_header, classes="dim")
            yield Label(f"+{self._plus_count} -{self._minus_count} will be reverted from the working tree")
            yield Label("y/Enter = yes, n/Esc = cancel", classes="dim")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
