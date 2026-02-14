from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Center, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ShowScreen(ModalScreen[None]):
    """Read-only modal showing formatted zettel content."""

    CSS = """
    ShowScreen { align: center middle; }
    #show-dialog { width: 80; max-height: 85%; padding: 1 2; border: thick $accent; background: $surface; }
    #show-content { height: auto; }
    #show-close { margin-top: 1; }
    """

    BINDINGS = [("escape", "close", "Close")]

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        from bim.commands.show_note.show_note import show_single

        content = show_single(self._path, quiet=True)
        with VerticalScroll(id="show-dialog"):
            yield Static(content, id="show-content", markup=False)
            with Center(id="show-close"):
                yield Button("Close", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
