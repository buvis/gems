from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

__all__ = ["CommitModal"]


class CommitModal(ModalScreen[str | None]):
    """Modal for entering a commit message."""

    CSS = """
    CommitModal {
        align: center middle;
    }
    CommitModal > Vertical {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Commit message:")
            yield Input(placeholder="Enter commit message...", id="commit-input")
            yield Label("Enter to commit, Esc to cancel", classes="dim")

    def on_mount(self) -> None:
        self.query_one("#commit-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.dismiss(event.value.strip())

    def action_cancel(self) -> None:
        self.dismiss(None)
