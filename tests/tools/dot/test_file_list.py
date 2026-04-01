from __future__ import annotations

import pytest
from dot.tui.models import FileEntry
from dot.tui.widgets.file_list import FileListWidget
from textual.app import App, ComposeResult


def _entries(*specs: tuple[str, str, bool]) -> list[FileEntry]:
    return [FileEntry(path=p, status=s, is_secret=sec) for p, s, sec in specs]


class FileListHost(App[None]):
    """Minimal host app for testing FileListWidget."""

    def __init__(
        self,
        title: str,
        files: list[FileEntry],
        *,
        staged: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._files = files
        self._staged = staged
        self.messages: list[FileListWidget.FileSelected] = []

    def compose(self) -> ComposeResult:
        yield FileListWidget(self._title, staged=self._staged)

    def on_mount(self) -> None:
        self.query_one(FileListWidget).update_files(self._files)

    def on_file_list_widget_file_selected(
        self,
        event: FileListWidget.FileSelected,
    ) -> None:
        self.messages.append(event)


class TestFileListWidget:
    @pytest.mark.anyio
    async def test_renders_file_paths(self) -> None:
        files = _entries((".bashrc", "M ", False), (".zshrc", " M", False))
        app = FileListHost("Unstaged", files)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            text = widget.render().plain if hasattr(widget.render(), "plain") else str(widget.render())
            assert ".bashrc" in text
            assert ".zshrc" in text

    @pytest.mark.anyio
    async def test_j_moves_cursor_down(self) -> None:
        files = _entries(("a", "M ", False), ("b", "M ", False), ("c", "M ", False))
        app = FileListHost("Unstaged", files)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            assert widget.cursor_index == 0
            await pilot.press("j")
            assert widget.cursor_index == 1
            await pilot.press("j")
            assert widget.cursor_index == 2

    @pytest.mark.anyio
    async def test_k_moves_cursor_up(self) -> None:
        files = _entries(("a", "M ", False), ("b", "M ", False), ("c", "M ", False))
        app = FileListHost("Unstaged", files)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            widget.cursor_index = 2
            await pilot.pause()
            await pilot.press("k")
            assert widget.cursor_index == 1
            await pilot.press("k")
            assert widget.cursor_index == 0

    @pytest.mark.anyio
    async def test_cursor_wraps_at_bottom(self) -> None:
        files = _entries(("a", "M ", False), ("b", "M ", False))
        app = FileListHost("Unstaged", files)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            widget.cursor_index = 1
            await pilot.pause()
            await pilot.press("j")
            assert widget.cursor_index == 0

    @pytest.mark.anyio
    async def test_cursor_wraps_at_top(self) -> None:
        files = _entries(("a", "M ", False), ("b", "M ", False))
        app = FileListHost("Unstaged", files)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            assert widget.cursor_index == 0
            await pilot.press("k")
            assert widget.cursor_index == 1

    @pytest.mark.anyio
    async def test_empty_list_shows_no_changes(self) -> None:
        app = FileListHost("Unstaged", [])
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            text = widget.render().plain if hasattr(widget.render(), "plain") else str(widget.render())
            assert "No changes" in text

    @pytest.mark.anyio
    async def test_file_selected_message_on_cursor_change(self) -> None:
        files = _entries(("a", "M ", False), ("b", " M", False))
        app = FileListHost("Staged", files, staged=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.messages.clear()
            await pilot.press("j")
            await pilot.pause()
            assert len(app.messages) >= 1
            msg = app.messages[-1]
            assert msg.entry == files[1]
            assert msg.staged is True

    @pytest.mark.anyio
    async def test_secret_badge_visible(self) -> None:
        files = _entries((".env", "??", True))
        app = FileListHost("Unstaged", files)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            text = widget.render().plain if hasattr(widget.render(), "plain") else str(widget.render())
            assert "secret" in text.lower()

    @pytest.mark.anyio
    async def test_title_rendered(self) -> None:
        files = _entries(("a", "M ", False))
        app = FileListHost("Staged", files, staged=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.query_one(FileListWidget)
            text = widget.render().plain if hasattr(widget.render(), "plain") else str(widget.render())
            assert "Staged" in text
