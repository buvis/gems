from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from dot.cli import cli
from dot.tui.models import BranchInfo


def _mock_git_ops() -> MagicMock:
    ops = MagicMock()
    ops.status.return_value = []
    ops.branch_info.return_value = BranchInfo(name="master")
    ops.diff.return_value = ""
    return ops


class TestDotApp:
    @pytest.mark.anyio
    async def test_app_launches(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), \
             patch("dot.tui.app.GitOps") as mock_git_ops_cls:
            mock_git_ops_cls.return_value = _mock_git_ops()

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()

    @pytest.mark.anyio
    async def test_q_quits(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), \
             patch("dot.tui.app.GitOps") as mock_git_ops_cls:
            mock_git_ops_cls.return_value = _mock_git_ops()

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                await pilot.press("q")
                await pilot.pause()
                assert not app.is_running

    @pytest.mark.anyio
    async def test_main_screen_active_on_mount(self) -> None:
        from dot.tui.app import DotApp
        from dot.tui.screens.main import MainScreen

        with patch("dot.tui.app.ShellAdapter"), \
             patch("dot.tui.app.GitOps") as mock_git_ops_cls:
            mock_git_ops_cls.return_value = _mock_git_ops()

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                assert isinstance(app.screen, MainScreen)


class TestDotCli:
    def test_tui_help(self, runner) -> None:
        result = runner.invoke(cli, ["tui", "--help"])
        assert result.exit_code == 0

    def test_bare_dot_launches_tui(self, runner, mocker) -> None:
        mock_app_cls = mocker.patch("dot.cli.DotApp")
        mock_app_instance = MagicMock()
        mock_app_cls.return_value = mock_app_instance

        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        mock_app_instance.run.assert_called_once()

    def test_status_does_not_launch_tui(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.status.status.CommandStatus")
        mock_cmd_cls.return_value.execute.return_value = MagicMock(
            success=True, output="ok", warnings=[], error=None, metadata={}
        )

        with patch("dot.cli.DotApp") as mock_app_cls:
            runner.invoke(cli, ["status"])
            mock_app_cls.assert_not_called()
