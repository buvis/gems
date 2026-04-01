from __future__ import annotations

from typing import TYPE_CHECKING

from buvis.pybase.adapters import ShellAdapter
from textual.app import App
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label

from dot.tui.git_ops import GitOps
from dot.tui.screens.main import MainScreen

if TYPE_CHECKING:
    from textual.app import ComposeResult

__all__ = ["DotApp"]


class _ConfirmQuitScreen(ModalScreen[bool]):
    """Confirmation dialog shown when quitting with unpushed work."""

    CSS = """
    _ConfirmQuitScreen {
        align: center middle;
    }
    #confirm-box {
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
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self._message)
            yield Label("y = quit, n/Esc = cancel", classes="dim")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class DotApp(App[None]):
    """Dotfiles TUI application."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, dotfiles_root: str, theme: str = "textual-dark") -> None:
        super().__init__()
        shell = ShellAdapter(suppress_logging=True)
        self._git_ops = GitOps(shell, dotfiles_root)
        self.theme = theme

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self._git_ops))

    async def action_quit(self) -> None:
        uncommitted = self._git_ops.has_uncommitted_changes()
        unpushed = self._git_ops.has_unpushed_commits()

        if not uncommitted and not unpushed:
            self.exit()
            return

        warnings: list[str] = []
        if uncommitted:
            warnings.append("uncommitted changes")
        if unpushed:
            warnings.append("unpushed commits")

        msg = f"You have {' and '.join(warnings)}. Quit anyway?"

        def _on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self.exit()

        self.push_screen(_ConfirmQuitScreen(msg), callback=_on_confirm)
