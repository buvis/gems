from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bim.tui.show_note import ShowScreen
from buvis.pybase.result import CommandResult
from textual.app import App, ComposeResult
from textual.widgets import Button, Static


class ShowHost(App[None]):
    """Minimal host app to test ShowScreen modal."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self.dismissed = False

    def compose(self) -> ComposeResult:
        yield Button("trigger")

    def on_mount(self) -> None:
        self.push_screen(ShowScreen(self._path), callback=self._on_dismiss)

    def _on_dismiss(self, _result: None) -> None:
        self.dismissed = True
        self.exit()


class TestShowScreen:
    @pytest.mark.anyio
    async def test_compose_renders_content(self):
        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd_cls,
            patch("bim.dependencies.get_repo") as mock_repo,
            patch("bim.dependencies.get_formatter") as mock_fmt,
        ):
            mock_repo.return_value = MagicMock()
            mock_fmt.return_value = MagicMock()
            mock_cmd_cls.return_value.execute.return_value = CommandResult(
                success=True, output="# Test Note\nBody text"
            )

            app = ShowHost(Path("/tmp/test.md"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                screen = app.screen
                content = screen.query_one("#show-content", Static)
                assert "Test Note" in content.renderable

    @pytest.mark.anyio
    async def test_close_button_dismisses(self):
        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd_cls,
            patch("bim.dependencies.get_repo"),
            patch("bim.dependencies.get_formatter"),
        ):
            mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="content")

            app = ShowHost(Path("/tmp/test.md"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.click("#close-btn")
                await pilot.pause()
            assert app.dismissed is True

    @pytest.mark.anyio
    async def test_escape_dismisses(self):
        with (
            patch("bim.commands.show_note.show_note.CommandShowNote") as mock_cmd_cls,
            patch("bim.dependencies.get_repo"),
            patch("bim.dependencies.get_formatter"),
        ):
            mock_cmd_cls.return_value.execute.return_value = CommandResult(success=True, output="content")

            app = ShowHost(Path("/tmp/test.md"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
            assert app.dismissed is True
