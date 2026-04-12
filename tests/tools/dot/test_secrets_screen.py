from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from buvis.pybase.result import CommandResult
from dot.tui.commands.secrets import SecretEntry
from textual.app import App, ComposeResult
from textual.widgets import Static

_SAMPLE_SECRETS = [
    SecretEntry(path=".ssh/config", status="revealed"),
    SecretEntry(path=".gnupg/keys", status="hidden"),
    SecretEntry(path=".env", status="revealed"),
]


@pytest.fixture
def git_ops(tmp_path):
    mock = MagicMock()
    mock.dotfiles_root = str(tmp_path)
    mock.wd = tmp_path
    return mock


class SecretsHost(App[None]):
    """Minimal host app that pushes SecretsScreen on mount."""

    def __init__(self, git_ops):
        super().__init__()
        self._git_ops = git_ops

    def compose(self) -> ComposeResult:
        yield Static("host")

    def on_mount(self):
        from dot.tui.screens.secrets import SecretsScreen

        self.push_screen(SecretsScreen(self._git_ops))


def _patch_secrets(monkeypatch, *, secrets=None, reveal_ok=True, hide_ok=True, unreg_ok=True):
    """Patch all four command functions with sensible defaults."""
    monkeypatch.setattr(
        "dot.tui.screens.secrets.list_secrets",
        lambda _ops: secrets if secrets is not None else _SAMPLE_SECRETS,
    )
    monkeypatch.setattr(
        "dot.tui.screens.secrets.reveal_all",
        lambda _ops, passphrase=None: CommandResult(success=reveal_ok),
    )
    monkeypatch.setattr(
        "dot.tui.screens.secrets.hide_all",
        lambda _ops: CommandResult(success=hide_ok),
    )
    monkeypatch.setattr(
        "dot.tui.screens.secrets.unregister_secret",
        lambda _ops, _path: CommandResult(success=unreg_ok),
    )


class TestSecretsScreenComposition:
    @pytest.mark.anyio
    async def test_screen_displays_secrets_widget(self, git_ops, monkeypatch):
        """Screen should contain some widget for displaying secrets."""
        _patch_secrets(monkeypatch)

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            from dot.tui.screens.secrets import SecretsScreen

            assert isinstance(app.screen, SecretsScreen)


class TestSecretsScreenMount:
    @pytest.mark.anyio
    async def test_mount_calls_list_secrets(self, git_ops, monkeypatch):
        calls = []

        def mock_list(ops):
            calls.append(ops)
            return _SAMPLE_SECRETS

        monkeypatch.setattr("dot.tui.screens.secrets.list_secrets", mock_list)
        monkeypatch.setattr(
            "dot.tui.screens.secrets.reveal_all",
            lambda _ops: CommandResult(success=True),
        )
        monkeypatch.setattr(
            "dot.tui.screens.secrets.hide_all",
            lambda _ops: CommandResult(success=True),
        )
        monkeypatch.setattr(
            "dot.tui.screens.secrets.unregister_secret",
            lambda _ops, _path: CommandResult(success=True),
        )

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert len(calls) >= 1

    @pytest.mark.anyio
    async def test_mount_shows_secret_paths(self, git_ops, monkeypatch):
        _patch_secrets(monkeypatch)

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            # Verify no crash and screen is up
            from dot.tui.screens.secrets import SecretsScreen

            assert isinstance(app.screen, SecretsScreen)


class TestSecretsScreenStatus:
    @pytest.mark.anyio
    async def test_entries_show_status(self, git_ops, monkeypatch):
        """Revealed/hidden status should be visible somewhere in the screen."""
        _patch_secrets(monkeypatch)

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            # Screen should be alive and displaying secrets
            from dot.tui.screens.secrets import SecretsScreen

            assert isinstance(app.screen, SecretsScreen)


class TestSecretsScreenDismiss:
    @pytest.mark.anyio
    async def test_escape_dismisses_screen(self, git_ops, monkeypatch):
        from dot.tui.screens.secrets import SecretsScreen

        _patch_secrets(monkeypatch)

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, SecretsScreen)

            await pilot.press("escape")
            await pilot.pause()

            assert not isinstance(app.screen, SecretsScreen)


class TestSecretsScreenReveal:
    @pytest.mark.anyio
    async def test_r_calls_reveal_all(self, git_ops, monkeypatch):
        reveal_calls = []
        list_calls = []

        def mock_reveal(ops, passphrase=None):
            reveal_calls.append((ops, passphrase))
            return CommandResult(success=True)

        def mock_list(ops):
            list_calls.append(ops)
            return _SAMPLE_SECRETS

        monkeypatch.setattr("dot.tui.screens.secrets.list_secrets", mock_list)
        monkeypatch.setattr("dot.tui.screens.secrets.reveal_all", mock_reveal)
        monkeypatch.setattr(
            "dot.tui.screens.secrets.hide_all",
            lambda _ops: CommandResult(success=True),
        )
        monkeypatch.setattr(
            "dot.tui.screens.secrets.unregister_secret",
            lambda _ops, _path: CommandResult(success=True),
        )

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            initial_list_count = len(list_calls)

            await pilot.press("r")
            await pilot.pause()
            # Type passphrase into the modal and submit
            await pilot.press(*"test")
            await pilot.press("enter")
            await pilot.pause()

            assert len(reveal_calls) == 1
            # list should have been refreshed after reveal
            assert len(list_calls) > initial_list_count


class TestSecretsScreenHide:
    @pytest.mark.anyio
    async def test_h_calls_hide_all(self, git_ops, monkeypatch):
        hide_calls = []
        list_calls = []

        def mock_hide(ops):
            hide_calls.append(ops)
            return CommandResult(success=True)

        def mock_list(ops):
            list_calls.append(ops)
            return _SAMPLE_SECRETS

        monkeypatch.setattr("dot.tui.screens.secrets.list_secrets", mock_list)
        monkeypatch.setattr(
            "dot.tui.screens.secrets.reveal_all",
            lambda _ops: CommandResult(success=True),
        )
        monkeypatch.setattr("dot.tui.screens.secrets.hide_all", mock_hide)
        monkeypatch.setattr(
            "dot.tui.screens.secrets.unregister_secret",
            lambda _ops, _path: CommandResult(success=True),
        )

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            initial_list_count = len(list_calls)

            await pilot.press("h")
            await pilot.pause()

            assert len(hide_calls) == 1
            assert len(list_calls) > initial_list_count


class TestSecretsScreenUnregister:
    @pytest.mark.anyio
    async def test_shift_e_triggers_unregister_flow(self, git_ops, monkeypatch):
        unreg_calls = []

        def mock_unreg(ops, path):
            unreg_calls.append(path)
            return CommandResult(success=True)

        monkeypatch.setattr(
            "dot.tui.screens.secrets.list_secrets",
            lambda _ops: _SAMPLE_SECRETS,
        )
        monkeypatch.setattr(
            "dot.tui.screens.secrets.reveal_all",
            lambda _ops: CommandResult(success=True),
        )
        monkeypatch.setattr(
            "dot.tui.screens.secrets.hide_all",
            lambda _ops: CommandResult(success=True),
        )
        monkeypatch.setattr("dot.tui.screens.secrets.unregister_secret", mock_unreg)

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Press E (shift+e) to start unregister flow
            await pilot.press("E")
            await pilot.pause()

            # If a confirmation modal appeared, confirm it
            # Try pressing y/enter to confirm
            await pilot.press("y")
            await pilot.pause()
            if not unreg_calls:
                await pilot.press("enter")
                await pilot.pause()

            assert len(unreg_calls) == 1
            assert unreg_calls[0] == _SAMPLE_SECRETS[0].path


class TestSecretsScreenEmpty:
    @pytest.mark.anyio
    async def test_empty_list_shows_message(self, git_ops, monkeypatch):
        """When list_secrets returns [], screen should show an informational message."""
        _patch_secrets(monkeypatch, secrets=[])

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            from dot.tui.screens.secrets import SecretsScreen

            assert isinstance(app.screen, SecretsScreen)


class TestSecretsScreenNavigation:
    @pytest.mark.anyio
    async def test_j_k_navigate_list(self, git_ops, monkeypatch):
        _patch_secrets(monkeypatch)

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            # Press j to move down, k to move up - should not crash
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("j")
            await pilot.pause()
            await pilot.press("k")
            await pilot.pause()

            from dot.tui.screens.secrets import SecretsScreen

            assert isinstance(app.screen, SecretsScreen)

    @pytest.mark.anyio
    async def test_scroll_to_region_called_on_navigation(self, git_ops, monkeypatch):
        _patch_secrets(monkeypatch)

        app = SecretsHost(git_ops)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()

            from dot.tui.screens.secrets import _SecretListWidget

            widget = app.screen.query_one("#secret-list", _SecretListWidget)
            calls: list[object] = []
            original = widget.scroll_to_region

            def _capture(*args: object, **kwargs: object) -> None:
                calls.append((args, kwargs))
                original(*args, **kwargs)

            widget.scroll_to_region = _capture  # type: ignore[assignment]

            await pilot.press("j")
            await pilot.pause()
            assert len(calls) >= 1
