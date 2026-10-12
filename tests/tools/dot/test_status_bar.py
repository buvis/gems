from __future__ import annotations

import pytest
from dot.tui.models import BranchInfo
from dot.tui.widgets.status_bar import StatusBar
from textual.app import App, ComposeResult


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


class LinkProblemsHost(App[None]):
    def __init__(self, info: BranchInfo, link_problems: int | None = None, error: str | None = None) -> None:
        super().__init__()
        self._info = info
        self._link_problems = link_problems
        self._error = error

    def compose(self) -> ComposeResult:
        yield StatusBar()

    def on_mount(self) -> None:
        kwargs: dict[str, object] = {}
        if self._link_problems is not None:
            kwargs["link_problems"] = self._link_problems
        self.query_one(StatusBar).update_info(self._info, error=self._error, **kwargs)


class TestStatusBarLinkProblems:
    @pytest.mark.anyio
    async def test_renders_link_problem_count_when_nonzero(self) -> None:
        app = LinkProblemsHost(BranchInfo(name="main"), link_problems=1)
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "1 link problem(s)" in text

    @pytest.mark.anyio
    async def test_renders_exact_link_problem_count(self) -> None:
        app = LinkProblemsHost(BranchInfo(name="main"), link_problems=4)
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "4 link problem(s)" in text

    @pytest.mark.anyio
    async def test_hides_link_problems_when_zero(self) -> None:
        app = LinkProblemsHost(BranchInfo(name="main"), link_problems=0)
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "link problem" not in text

    @pytest.mark.anyio
    async def test_hides_link_problems_by_default(self) -> None:
        app = LinkProblemsHost(BranchInfo(name="main"))
        async with app.run_test(size=(80, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "link problem" not in text

    @pytest.mark.anyio
    async def test_orders_secrets_then_link_problems_then_error(self) -> None:
        app = LinkProblemsHost(BranchInfo(name="main", secret_count=2), link_problems=1, error="boom")
        async with app.run_test(size=(120, 4)) as pilot:
            await pilot.pause()
            text = str(app.query_one(StatusBar).render())
            assert "secret" in text.lower()
            assert text.lower().index("secret") < text.index("link problem") < text.index("boom")
