from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

__all__ = ["GitignoreModal"]


class GitignoreModal(ModalScreen[str | None]):
    """Modal for adding a pattern to .gitignore."""

    CSS = """
    GitignoreModal {
        align: center middle;
    }
    GitignoreModal > Vertical {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, default_pattern: str) -> None:
        super().__init__()
        self._default_pattern = default_pattern

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Add to .gitignore:")
            yield Input(value=self._default_pattern, id="pattern-input")
            yield Label("Enter to confirm, Esc to cancel", classes="dim")

    def on_mount(self) -> None:
        self.query_one("#pattern-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
