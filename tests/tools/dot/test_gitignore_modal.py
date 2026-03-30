from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from dot.tui.widgets.gitignore_modal import GitignoreModal


class ModalHost(App[None]):
    def __init__(self, default_pattern: str) -> None:
        super().__init__()
        self._default_pattern = default_pattern
        self.dismissed_value: str | None = "NOT_SET"

    def compose(self) -> ComposeResult:
        yield Static("host")

    def on_mount(self) -> None:
        self.push_screen(
            GitignoreModal(self._default_pattern),
            callback=self._on_dismiss,
        )

    def _on_dismiss(self, value: str | None) -> None:
        self.dismissed_value = value


class TestGitignoreModal:
    @pytest.mark.anyio
    async def test_default_pattern_prefills_input(self) -> None:
        app = ModalHost("myfile.txt")
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            from textual.widgets import Input
            inp = app.screen.query_one("#pattern-input", Input)
            assert inp.value == "myfile.txt"

    @pytest.mark.anyio
    async def test_enter_dismisses_with_value(self) -> None:
        app = ModalHost("test.log")
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.dismissed_value == "test.log"

    @pytest.mark.anyio
    async def test_escape_dismisses_with_none(self) -> None:
        app = ModalHost("test.log")
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.dismissed_value is None

    @pytest.mark.anyio
    async def test_edited_value_returned(self) -> None:
        app = ModalHost("original")
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            from textual.widgets import Input
            inp = app.screen.query_one("#pattern-input", Input)
            inp.value = "edited_pattern"
            await pilot.press("enter")
            await pilot.pause()
            assert app.dismissed_value == "edited_pattern"

    @pytest.mark.anyio
    async def test_empty_pattern_does_not_dismiss(self) -> None:
        app = ModalHost("")
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.dismissed_value == "NOT_SET"

    @pytest.mark.anyio
    async def test_whitespace_pattern_does_not_dismiss(self) -> None:
        app = ModalHost("  ")
        async with app.run_test(size=(80, 10)) as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.dismissed_value == "NOT_SET"
