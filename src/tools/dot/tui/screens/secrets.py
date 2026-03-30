from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Footer, Label

from dot.tui.commands.secrets import (
    SecretEntry,
    hide_all,
    list_secrets,
    reveal_all,
    unregister_secret,
)
from dot.tui.widgets.passphrase_modal import PassphraseModal

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from dot.tui.git_ops import GitOps

__all__ = ["SecretsScreen"]


class _ConfirmUnregisterScreen(ModalScreen[bool]):
    """Yes/no confirmation for secret unregistration."""

    CSS = """
    _ConfirmUnregisterScreen {
        align: center middle;
    }
    #confirm-box {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("enter", "confirm", "Confirm"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(f"Unregister secret '{self._path}'?")
            yield Label("y/Enter = yes, n/Esc = cancel", classes="dim")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class _SecretListWidget(Widget, can_focus=True):
    """Simple navigable list of secret entries."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries: list[SecretEntry] = []
        self._cursor: int = 0

    def update_entries(self, entries: list[SecretEntry]) -> None:
        self._entries = list(entries)
        if self._entries:
            self._cursor = min(self._cursor, len(self._entries) - 1)
        else:
            self._cursor = 0
        self.refresh()

    @property
    def selected_entry(self) -> SecretEntry | None:
        if not self._entries:
            return None
        return self._entries[self._cursor]

    def move_down(self) -> None:
        if not self._entries:
            return
        self._cursor = (self._cursor + 1) % len(self._entries)
        self.refresh()

    def move_up(self) -> None:
        if not self._entries:
            return
        self._cursor = (self._cursor - 1) % len(self._entries)
        self.refresh()

    def render(self) -> Text:
        if not self._entries:
            return Text("No secrets registered")
        lines: list[str] = []
        for i, entry in enumerate(self._entries):
            indicator = ">" if i == self._cursor else " "
            icon = "\u25cf" if entry.status == "revealed" else "\u25cb"
            lines.append(f"{indicator} {icon} {entry.path} [{entry.status}]")
        return Text("\n".join(lines))


class SecretsScreen(Screen):
    """Screen for managing git-secret entries."""

    BINDINGS = [
        Binding("escape", "dismiss_screen", "Back"),
        Binding("r", "reveal", "Reveal all"),
        Binding("h", "hide", "Hide all"),
        Binding("E", "unregister", "Unregister", key_display="E"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
    ]

    def __init__(self, git_ops: GitOps) -> None:
        super().__init__()
        self._git_ops = git_ops

    def compose(self) -> ComposeResult:
        yield _SecretListWidget(id="secret-list")
        yield Label("", id="secrets-status")
        yield Footer()

    def render(self) -> str:
        widget = self.query_one("#secret-list", _SecretListWidget)
        return widget.render().plain

    def on_mount(self) -> None:
        self._refresh_list()
        self.query_one("#secret-list", _SecretListWidget).focus()

    def _show_message(self, msg: str) -> None:
        self.query_one("#secrets-status", Label).update(msg)

    def _refresh_list(self) -> None:
        entries = list_secrets(self._git_ops)
        self.query_one("#secret-list", _SecretListWidget).update_entries(entries)

    def action_dismiss_screen(self) -> None:
        self.dismiss()

    def action_reveal(self) -> None:
        def _on_passphrase(passphrase: str | None) -> None:
            if passphrase is None:
                return
            result = reveal_all(self._git_ops, passphrase=passphrase)
            if not result.success:
                self._show_message(f"Reveal failed: {result.error}")
                return
            self._refresh_list()

        self.app.push_screen(PassphraseModal(), callback=_on_passphrase)

    def action_hide(self) -> None:
        result = hide_all(self._git_ops)
        if not result.success:
            self._show_message(f"Hide failed: {result.error}")
            return
        self._refresh_list()

    def action_unregister(self) -> None:
        widget = self.query_one("#secret-list", _SecretListWidget)
        entry = widget.selected_entry
        if entry is None:
            return

        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            result = unregister_secret(self._git_ops, entry.path)
            if not result.success:
                self._show_message(f"Unregister failed: {result.error}")
                return
            self._refresh_list()

        self.app.push_screen(_ConfirmUnregisterScreen(entry.path), callback=_on_confirm)

    def action_cursor_down(self) -> None:
        self.query_one("#secret-list", _SecretListWidget).move_down()

    def action_cursor_up(self) -> None:
        self.query_one("#secret-list", _SecretListWidget).move_up()
