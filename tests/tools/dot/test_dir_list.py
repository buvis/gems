from __future__ import annotations

import pytest
from dot.tui.commands.browse import DirEntry, TrackingStatus
from dot.tui.widgets.dir_list import DirListWidget
from rich.text import Text
from textual.app import App, ComposeResult
from textual.geometry import Region


def _entry(
    name: str,
    *,
    is_dir: bool = False,
    status: TrackingStatus = TrackingStatus.TRACKED,
) -> DirEntry:
    return DirEntry(name=name, path=f"/home/user/{name}", is_dir=is_dir, status=status)


def _entries(*specs: tuple[str, bool, TrackingStatus]) -> list[DirEntry]:
    return [_entry(name, is_dir=d, status=s) for name, d, s in specs]


class DirListHost(App[None]):
    """Minimal host app for testing DirListWidget."""

    def __init__(self, entries: list[DirEntry]) -> None:
        super().__init__()
        self._entries = entries
        self.messages: list[DirListWidget.DirEntrySelected] = []

    def compose(self) -> ComposeResult:
        yield DirListWidget()

    def on_mount(self) -> None:
        self.query_one(DirListWidget).update_entries(self._entries)

    def on_dir_list_widget_dir_entry_selected(
        self,
        event: DirListWidget.DirEntrySelected,
    ) -> None:
        self.messages.append(event)


def _render_plain(widget: DirListWidget) -> str:
    result = widget.render()
    if isinstance(result, Text):
        return result.plain
    return str(result)


class TestDirListWidget:
    @pytest.mark.anyio
    async def test_renders_entry_names(self) -> None:
        entries = _entries(
            (".bashrc", False, TrackingStatus.TRACKED),
            (".zshrc", False, TrackingStatus.UNTRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            text = _render_plain(app.query_one(DirListWidget))
            assert ".bashrc" in text
            assert ".zshrc" in text

    @pytest.mark.anyio
    async def test_directory_entries_show_trailing_slash(self) -> None:
        entries = _entries(
            ("config", True, TrackingStatus.TRACKED),
            (".bashrc", False, TrackingStatus.TRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            text = _render_plain(app.query_one(DirListWidget))
            assert "config/" in text
            assert ".bashrc" in text
            assert ".bashrc/" not in text

    @pytest.mark.anyio
    async def test_tracked_entry_styled_green(self) -> None:
        entries = [_entry(".bashrc", status=TrackingStatus.TRACKED)]
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            result = app.query_one(DirListWidget).render()
            assert isinstance(result, Text)
            styles = [span.style for span in result._spans]
            green_found = any("green" in str(s) for s in styles)
            assert green_found, f"Expected green style for tracked entry, got: {styles}"

    @pytest.mark.anyio
    async def test_untracked_entry_styled_yellow(self) -> None:
        entries = [_entry(".newrc", status=TrackingStatus.UNTRACKED)]
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            result = app.query_one(DirListWidget).render()
            assert isinstance(result, Text)
            styles = [span.style for span in result._spans]
            yellow_found = any("yellow" in str(s) for s in styles)
            assert yellow_found, f"Expected yellow style for untracked entry, got: {styles}"

    @pytest.mark.anyio
    async def test_ignored_entry_styled_dim(self) -> None:
        entries = [_entry(".DS_Store", status=TrackingStatus.IGNORED)]
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            result = app.query_one(DirListWidget).render()
            assert isinstance(result, Text)
            styles = [span.style for span in result._spans]
            dim_found = any("dim" in str(s) for s in styles)
            assert dim_found, f"Expected dim style for ignored entry, got: {styles}"

    @pytest.mark.anyio
    async def test_j_moves_cursor_down(self) -> None:
        entries = _entries(
            ("a", False, TrackingStatus.TRACKED),
            ("b", False, TrackingStatus.TRACKED),
            ("c", False, TrackingStatus.TRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(DirListWidget)
            assert widget.cursor_index == 0
            await pilot.press("j")
            assert widget.cursor_index == 1
            await pilot.press("j")
            assert widget.cursor_index == 2

    @pytest.mark.anyio
    async def test_k_moves_cursor_up(self) -> None:
        entries = _entries(
            ("a", False, TrackingStatus.TRACKED),
            ("b", False, TrackingStatus.TRACKED),
            ("c", False, TrackingStatus.TRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(DirListWidget)
            widget.cursor_index = 2
            await pilot.pause()
            await pilot.press("k")
            assert widget.cursor_index == 1
            await pilot.press("k")
            assert widget.cursor_index == 0

    @pytest.mark.anyio
    async def test_cursor_wraps_at_bottom(self) -> None:
        entries = _entries(
            ("a", False, TrackingStatus.TRACKED),
            ("b", False, TrackingStatus.TRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(DirListWidget)
            widget.cursor_index = 1
            await pilot.pause()
            await pilot.press("j")
            assert widget.cursor_index == 0

    @pytest.mark.anyio
    async def test_cursor_wraps_at_top(self) -> None:
        entries = _entries(
            ("a", False, TrackingStatus.TRACKED),
            ("b", False, TrackingStatus.TRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(DirListWidget)
            assert widget.cursor_index == 0
            await pilot.press("k")
            assert widget.cursor_index == 1

    @pytest.mark.anyio
    async def test_dir_entry_selected_message_on_cursor_change(self) -> None:
        entries = _entries(
            ("a", False, TrackingStatus.TRACKED),
            ("b", True, TrackingStatus.UNTRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.messages.clear()
            await pilot.press("j")
            await pilot.pause()
            assert len(app.messages) >= 1
            msg = app.messages[-1]
            assert msg.entry == entries[1]

    @pytest.mark.anyio
    async def test_empty_list_shows_placeholder(self) -> None:
        app = DirListHost([])
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            text = _render_plain(app.query_one(DirListWidget))
            assert text.strip() != ""

    @pytest.mark.anyio
    async def test_selected_entry_returns_current(self) -> None:
        entries = _entries(
            ("a", False, TrackingStatus.TRACKED),
            ("b", False, TrackingStatus.UNTRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(DirListWidget)
            assert widget.selected_entry == entries[0]
            await pilot.press("j")
            assert widget.selected_entry == entries[1]

    @pytest.mark.anyio
    async def test_selected_entry_none_when_empty(self) -> None:
        app = DirListHost([])
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(DirListWidget)
            assert widget.selected_entry is None

    @pytest.mark.anyio
    async def test_scroll_to_region_called_on_cursor_change(self) -> None:
        entries = _entries(
            ("a", False, TrackingStatus.TRACKED),
            ("b", False, TrackingStatus.TRACKED),
            ("c", False, TrackingStatus.TRACKED),
        )
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(DirListWidget)
            calls: list[tuple[object, ...]] = []
            original = widget.scroll_to_region

            def _capture(*args: object, **kwargs: object) -> None:
                calls.append(args)
                original(*args, **kwargs)

            widget.scroll_to_region = _capture  # type: ignore[assignment]
            await pilot.press("j")
            await pilot.pause()
            assert len(calls) >= 1
            region = calls[-1][0]
            assert isinstance(region, Region)
            assert region.y == 1  # cursor moved from 0 to 1

    @pytest.mark.anyio
    async def test_parent_dir_entry_renders(self) -> None:
        parent = DirEntry(name="..", path="/home/user", is_dir=True, status=TrackingStatus.TRACKED)
        entries = [parent, _entry(".bashrc")]
        app = DirListHost(entries)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            text = _render_plain(app.query_one(DirListWidget))
            assert ".." in text
