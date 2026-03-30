from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from dot.tui.models import BranchInfo
from dot.tui.widgets.status_bar import StatusBar


class StatusBarHost(App[None]):
    def __init__(self, info: BranchInfo | None = None) -> None:
        super().__init__()
        self._info = info

    def compose(self) -> ComposeResult:
        yield StatusBar()

    def on_mount(self) -> None:
        if self._info is not None:
            self.query_one(StatusBar).update_info(self._info)


class TestStatusBar:
    @pytest.mark.anyio
    async def test_renders_branch_name(self) -> None:
        app = StatusBarHost(BranchInfo(name="master"))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            widget = app.query_one(StatusBar)
            text = str(widget.render())
            assert "master" in text

    @pytest.mark.anyio
    async def test_renders_ahead_when_nonzero(self) -> None:
        app = StatusBarHost(BranchInfo(name="main", ahead=3))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "3" in text

    @pytest.mark.anyio
    async def test_renders_behind_when_nonzero(self) -> None:
        app = StatusBarHost(BranchInfo(name="main", behind=2))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "2" in text

    @pytest.mark.anyio
    async def test_hides_ahead_when_zero(self) -> None:
        app = StatusBarHost(BranchInfo(name="main", ahead=0))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "ahead" not in text.lower()

    @pytest.mark.anyio
    async def test_hides_behind_when_zero(self) -> None:
        app = StatusBarHost(BranchInfo(name="main", behind=0))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "behind" not in text.lower()

    @pytest.mark.anyio
    async def test_renders_secret_count_when_nonzero(self) -> None:
        app = StatusBarHost(BranchInfo(name="main", secret_count=5))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "5" in text

    @pytest.mark.anyio
    async def test_hides_secrets_when_zero(self) -> None:
        app = StatusBarHost(BranchInfo(name="main", secret_count=0))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "secret" not in text.lower()
