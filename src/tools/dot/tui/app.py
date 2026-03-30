from __future__ import annotations

from buvis.pybase.adapters import ShellAdapter
from textual.app import App
from textual.binding import Binding

from dot.tui.git_ops import GitOps
from dot.tui.screens.main import MainScreen

__all__ = ["DotApp"]


class DotApp(App):
    """Dotfiles TUI application."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, dotfiles_root: str) -> None:
        super().__init__()
        shell = ShellAdapter(suppress_logging=True)
        self._git_ops = GitOps(shell, dotfiles_root)

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self._git_ops))
