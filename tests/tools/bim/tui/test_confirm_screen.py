from __future__ import annotations

import pytest
from bim.tui.query import ConfirmScreen
from textual.app import App, ComposeResult
from textual.widgets import Button


class ConfirmHost(App[bool | None]):
    """Minimal host app to test ConfirmScreen modal."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message
        self.result: bool | None = None

    def compose(self) -> ComposeResult:
        yield Button("trigger")

    def on_mount(self) -> None:
        self.push_screen(ConfirmScreen(self._message), callback=self._on_result)

    def _on_result(self, value: bool | None) -> None:
        self.result = value
        self.exit()


class TestConfirmScreen:
    @pytest.mark.anyio
    async def test_yes_dismisses_true(self):
        app = ConfirmHost("Delete?")
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.click("#yes")
            await pilot.pause()
        assert app.result is True

    @pytest.mark.anyio
    async def test_no_dismisses_false(self):
        app = ConfirmHost("Delete?")
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.click("#no")
            await pilot.pause()
        assert app.result is False
