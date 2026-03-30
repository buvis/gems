from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from buvis.pybase.result import CommandResult
from dot.tui.commands.browse import DirEntry, TrackingStatus
from dot.tui.widgets.dir_list import DirListWidget


def _entry(
    name: str,
    path: str,
    *,
    is_dir: bool = False,
    status: TrackingStatus = TrackingStatus.UNTRACKED,
) -> DirEntry:
    return DirEntry(name=name, path=path, is_dir=is_dir, status=status)


@pytest.fixture
def git_ops(tmp_path):
    mock = MagicMock()
    mock.dotfiles_root = str(tmp_path)
    mock._wd = tmp_path
    mock.stage.return_value = CommandResult(success=True)
    mock.add_to_gitignore.return_value = CommandResult(success=True)
    return mock


def _make_root_entries(tmp_path):
    """Entries returned when listing dotfiles_root."""
    return [
        _entry("..", str(tmp_path.parent), is_dir=True),
        _entry(".bashrc", str(tmp_path / ".bashrc"), status=TrackingStatus.TRACKED),
        _entry(".config", str(tmp_path / ".config"), is_dir=True, status=TrackingStatus.UNTRACKED),
        _entry(".zshrc", str(tmp_path / ".zshrc"), status=TrackingStatus.UNTRACKED),
    ]


def _make_subdir_entries(tmp_path):
    """Entries returned when listing a subdirectory."""
    return [
        _entry("..", str(tmp_path), is_dir=True),
        _entry("settings.json", str(tmp_path / ".config" / "settings.json"), status=TrackingStatus.TRACKED),
        _entry("theme.toml", str(tmp_path / ".config" / "theme.toml"), status=TrackingStatus.UNTRACKED),
    ]


class BrowseHost(App[None]):
    """Minimal host app that pushes BrowseScreen on mount."""

    def __init__(self, git_ops):
        super().__init__()
        self._git_ops = git_ops

    def compose(self) -> ComposeResult:
        yield Static("host")

    def on_mount(self):
        from dot.tui.screens.browse import BrowseScreen

        self.push_screen(BrowseScreen(self._git_ops))


class TestBrowseScreenComposition:
    @pytest.mark.anyio
    async def test_screen_contains_dir_list_widget(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        monkeypatch.setattr(
            "dot.tui.screens.browse.list_directory",
            lambda _ops, _path: root_entries,
        )

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widgets = app.screen.query(DirListWidget)
            assert len(widgets) > 0


class TestBrowseScreenInitialListing:
    @pytest.mark.anyio
    async def test_mount_lists_dotfiles_root(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        calls = []

        def mock_list_dir(ops, path):
            calls.append(path)
            return root_entries

        monkeypatch.setattr("dot.tui.screens.browse.list_directory", mock_list_dir)

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert calls[0] == str(tmp_path)

    @pytest.mark.anyio
    async def test_mount_populates_dir_list(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        monkeypatch.setattr(
            "dot.tui.screens.browse.list_directory",
            lambda _ops, _path: root_entries,
        )

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            widget = app.screen.query_one(DirListWidget)
            assert widget.selected_entry is not None


class TestBrowseScreenNavigation:
    @pytest.mark.anyio
    async def test_enter_on_directory_drills_in(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        subdir_entries = _make_subdir_entries(tmp_path)
        config_path = str(tmp_path / ".config")
        calls = []

        def mock_list_dir(ops, path):
            calls.append(path)
            if path == config_path:
                return subdir_entries
            return root_entries

        monkeypatch.setattr("dot.tui.screens.browse.list_directory", mock_list_dir)

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Move cursor to .config (index 2: .., .bashrc, .config)
            await pilot.press("j")
            await pilot.press("j")
            await pilot.pause()

            widget = app.screen.query_one(DirListWidget)
            assert widget.selected_entry is not None
            assert widget.selected_entry.name == ".config"

            await pilot.press("enter")
            await pilot.pause()

            # list_directory should have been called with the .config path
            assert config_path in calls

    @pytest.mark.anyio
    async def test_enter_on_parent_goes_up(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        subdir_entries = _make_subdir_entries(tmp_path)
        config_path = str(tmp_path / ".config")
        calls = []

        def mock_list_dir(ops, path):
            calls.append(path)
            if path == config_path:
                return subdir_entries
            return root_entries

        monkeypatch.setattr("dot.tui.screens.browse.list_directory", mock_list_dir)

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Drill into .config
            await pilot.press("j")
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            # Cursor should be on ".." (first entry in subdir)
            widget = app.screen.query_one(DirListWidget)
            assert widget.selected_entry is not None
            assert widget.selected_entry.name == ".."

            calls.clear()
            await pilot.press("enter")
            await pilot.pause()

            # Should navigate back to parent (dotfiles_root)
            assert str(tmp_path) in calls

    @pytest.mark.anyio
    async def test_backspace_goes_to_parent(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        subdir_entries = _make_subdir_entries(tmp_path)
        config_path = str(tmp_path / ".config")
        calls = []

        def mock_list_dir(ops, path):
            calls.append(path)
            if path == config_path:
                return subdir_entries
            return root_entries

        monkeypatch.setattr("dot.tui.screens.browse.list_directory", mock_list_dir)

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Drill into .config first
            await pilot.press("j")
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            calls.clear()
            await pilot.press("backspace")
            await pilot.pause()

            # Should navigate to parent directory
            assert str(tmp_path) in calls


class TestBrowseScreenDismiss:
    @pytest.mark.anyio
    async def test_escape_dismisses_screen(self, git_ops, tmp_path, monkeypatch):
        from dot.tui.screens.browse import BrowseScreen

        root_entries = _make_root_entries(tmp_path)
        monkeypatch.setattr(
            "dot.tui.screens.browse.list_directory",
            lambda _ops, _path: root_entries,
        )

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, BrowseScreen)

            await pilot.press("escape")
            await pilot.pause()

            assert not isinstance(app.screen, BrowseScreen)


class TestBrowseScreenStaging:
    @pytest.mark.anyio
    async def test_a_stages_untracked_file(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        monkeypatch.setattr(
            "dot.tui.screens.browse.list_directory",
            lambda _ops, _path: root_entries,
        )

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Move to .zshrc (untracked, index 3: .., .bashrc, .config, .zshrc)
            await pilot.press("j")
            await pilot.press("j")
            await pilot.press("j")
            await pilot.pause()

            widget = app.screen.query_one(DirListWidget)
            assert widget.selected_entry is not None
            assert widget.selected_entry.name == ".zshrc"
            assert widget.selected_entry.status == TrackingStatus.UNTRACKED

            await pilot.press("a")
            await pilot.pause()

            git_ops.stage.assert_called_once_with(str(tmp_path / ".zshrc"))

    @pytest.mark.anyio
    async def test_a_does_nothing_for_tracked_file(self, git_ops, tmp_path, monkeypatch):
        root_entries = _make_root_entries(tmp_path)
        monkeypatch.setattr(
            "dot.tui.screens.browse.list_directory",
            lambda _ops, _path: root_entries,
        )

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Move to .bashrc (tracked, index 1)
            await pilot.press("j")
            await pilot.pause()

            widget = app.screen.query_one(DirListWidget)
            assert widget.selected_entry is not None
            assert widget.selected_entry.name == ".bashrc"
            assert widget.selected_entry.status == TrackingStatus.TRACKED

            await pilot.press("a")
            await pilot.pause()

            git_ops.stage.assert_not_called()


class TestBrowseScreenGitignore:
    @pytest.mark.anyio
    async def test_i_opens_gitignore_modal(self, git_ops, tmp_path, monkeypatch):
        from dot.tui.widgets.gitignore_modal import GitignoreModal

        root_entries = _make_root_entries(tmp_path)
        monkeypatch.setattr(
            "dot.tui.screens.browse.list_directory",
            lambda _ops, _path: root_entries,
        )

        app = BrowseHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Move to .zshrc (index 3)
            await pilot.press("j")
            await pilot.press("j")
            await pilot.press("j")
            await pilot.pause()

            widget = app.screen.query_one(DirListWidget)
            assert widget.selected_entry is not None
            assert widget.selected_entry.name == ".zshrc"

            await pilot.press("i")
            await pilot.pause()

            assert isinstance(app.screen, GitignoreModal)
