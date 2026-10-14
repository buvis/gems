"""Modal for resolving host-link collisions during pull."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from dot.hostlinks.rescue import Resolution

if TYPE_CHECKING:
    from textual.app import ComposeResult

__all__ = ["RescueCollisionModal"]


class RescueCollisionModal(ModalScreen[Resolution]):
    """Modal for resolving a host-link collision during pull."""

    CSS = """
    RescueCollisionModal {
        align: center middle;
    }
    RescueCollisionModal > Vertical {
        width: auto;
        max-width: 80%;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    .dim {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("s", "keep_source", "Keep source"),
        Binding("t", "keep_target", "Keep target"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, target: str, source: str) -> None:
        """Initialize the modal.

        Args:
            target: The target path in conflict.
            source: The source path in conflict.
        """
        super().__init__()
        self._target = target
        self._source = source

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"Host-link collision: {self._target}")
            yield Label("Target and source both exist and differ:")
            yield Label(f"  target: {self._target}", classes="dim")
            yield Label(f"  source: {self._source}", classes="dim")
            yield Label("")
            yield Label("s = keep source (backup target)")
            yield Label("t = keep target (backup source)")
            yield Label("Esc = cancel pull")

    def action_keep_source(self) -> None:
        self.dismiss(Resolution.KEEP_SOURCE)

    def action_keep_target(self) -> None:
        self.dismiss(Resolution.KEEP_TARGET)

    def action_cancel(self) -> None:
        self.dismiss(Resolution.CANCEL)
