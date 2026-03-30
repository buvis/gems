from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from dot.tui.widgets.commit_modal import CommitModal


class ModalHost(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.dismissed_value: str | None = "NOT_SET"

    def compose(self) -> ComposeResult:
        yield Static("host")

    def on_mount(self) -> None:
        self.push_screen(CommitModal(), callback=self._on_dismiss)

    def _on_dismiss(self, value: str | None) -> None:
        self.dismissed_value = value


class TestCommitModal:
    @pytest.mark.anyio
    async def test_enter_with_text_dismisses(self) -> None:
        app = ModalHost()
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            from textual.widgets import Input
            inp = app.screen.query_one("#commit-input", Input)
            inp.value = "fix: something"
            await pilot.press("enter")
            await pilot.pause()
            assert app.dismissed_value == "fix: something"

    @pytest.mark.anyio
    async def test_escape_dismisses_with_none(self) -> None:
        app = ModalHost()
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.dismissed_value is None

    @pytest.mark.anyio
    async def test_enter_with_empty_does_not_dismiss(self) -> None:
        app = ModalHost()
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # Modal should still be showing (not dismissed)
            assert app.dismissed_value == "NOT_SET"

    @pytest.mark.anyio
    async def test_enter_with_whitespace_does_not_dismiss(self) -> None:
        app = ModalHost()
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            from textual.widgets import Input
            inp = app.screen.query_one("#commit-input", Input)
            inp.value = "   "
            await pilot.press("enter")
            await pilot.pause()
            assert app.dismissed_value == "NOT_SET"
