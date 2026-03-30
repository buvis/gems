from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label

__all__ = ["PassphraseModal"]


class PassphraseModal(ModalScreen[str | None]):
    """Modal for entering a GPG passphrase."""

    CSS = """
    PassphraseModal {
        align: center middle;
    }
    PassphraseModal > Vertical {
        width: auto;
        max-width: 80%;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("GPG passphrase:")
            yield Input(
                placeholder="Enter passphrase...",
                password=True,
                id="passphrase-input",
            )
            yield Label("Enter to confirm, Esc to cancel", classes="dim")

    def on_mount(self) -> None:
        self.query_one("#passphrase-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value:
            self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
