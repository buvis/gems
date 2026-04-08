from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.result import CommandResult
from dot.cli import cli
from dot.tui.models import BranchInfo, FileEntry


def _mock_git_ops(
    entries: list[FileEntry] | None = None,
) -> MagicMock:
    ops = MagicMock()
    ops.status.return_value = entries or []
    ops.branch_info.return_value = BranchInfo(name="master")
    ops.diff.return_value = ""
    ops.stage.return_value = CommandResult(success=True)
    ops.unstage.return_value = CommandResult(success=True)
    ops.has_uncommitted_changes.return_value = False
    ops.has_unpushed_commits.return_value = False
    ops.shell.is_command_available.return_value = False
    return ops


class TestDotApp:
    @pytest.mark.anyio
    async def test_app_launches(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_git_ops_cls:
            mock_git_ops_cls.return_value = _mock_git_ops()

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()

    @pytest.mark.anyio
    async def test_q_quits(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_git_ops_cls:
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

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_git_ops_cls:
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
        mock_app_instance = MagicMock()
        mocker.patch("dot.tui.app.DotApp", return_value=mock_app_instance)

        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        mock_app_instance.run.assert_called_once()

    def test_status_does_not_launch_tui(self, mocker, runner) -> None:
        mocker.patch("dot.cli.ShellAdapter")
        mock_cmd_cls = mocker.patch("dot.commands.status.status.CommandStatus")
        mock_cmd_cls.return_value.execute.return_value = MagicMock(
            success=True, output="ok", warnings=[], error=None, metadata={}
        )

        with patch("dot.tui.app.DotApp") as mock_app_cls:
            runner.invoke(cli, ["status"])
            mock_app_cls.assert_not_called()


_TEST_ENTRIES = [
    FileEntry(path="unstaged.txt", status=" M"),
    FileEntry(path="staged.txt", status="M "),
]


class TestMainScreen:
    @pytest.mark.anyio
    async def test_tab_cycles_focus(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            mock_cls.return_value = _mock_git_ops(_TEST_ENTRIES)

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                assert app.screen.focused is not None
                assert app.screen.focused.id == "unstaged"

                await pilot.press("tab")
                await pilot.pause()
                assert app.screen.focused is not None
                assert app.screen.focused.id == "staged"

                await pilot.press("tab")
                await pilot.pause()
                assert app.screen.focused is not None
                assert app.screen.focused.id == "diff"

                await pilot.press("tab")
                await pilot.pause()
                assert app.screen.focused is not None
                assert app.screen.focused.id == "unstaged"

    @pytest.mark.anyio
    async def test_stage_action_calls_git_ops(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                # Focus is on unstaged by default, press s to stage
                ops.status.reset_mock()
                await pilot.press("s")
                await pilot.pause()

                ops.stage.assert_called_once_with("unstaged.txt")
                # refresh_status calls status() again
                ops.status.assert_called()

    @pytest.mark.anyio
    async def test_unstage_action_calls_git_ops(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                # Move focus to staged list, then press u
                await pilot.press("tab")
                await pilot.pause()
                await pilot.press("u")
                await pilot.pause()

                ops.unstage.assert_called_once_with("staged.txt")

    @pytest.mark.anyio
    async def test_file_selected_updates_diff(self) -> None:
        from dot.tui.app import DotApp

        entries = [
            FileEntry(path="first.txt", status=" M"),
            FileEntry(path="second.txt", status=" M"),
        ]

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(entries)
            ops.diff.return_value = "diff --git a/second.txt"
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                # Move cursor down in unstaged list (j binding)
                ops.diff.reset_mock()
                await pilot.press("j")
                await pilot.pause()

                ops.diff.assert_called_with("second.txt", staged=False)

    @pytest.mark.anyio
    async def test_space_stages_from_unstaged(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                ops.stage.assert_called_once_with("unstaged.txt")

    @pytest.mark.anyio
    async def test_space_unstages_from_staged(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("tab")
                await pilot.pause()
                await pilot.press("space")
                await pilot.pause()
                ops.unstage.assert_called_once_with("staged.txt")

    @pytest.mark.anyio
    async def test_push_calls_git_ops(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            ops.push.return_value = CommandResult(success=True, output="Changes pushed")
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("p")
                await pilot.pause()
                ops.push.assert_called_once()

    @pytest.mark.anyio
    async def test_pull_calls_git_ops(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            ops.pull.return_value = CommandResult(success=True, output="Pulled")
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("P")
                await pilot.pause()
                ops.pull.assert_called_once()

    @pytest.mark.anyio
    async def test_refresh_updates_status(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                ops.status.reset_mock()
                await pilot.press("r")
                await pilot.pause()
                ops.status.assert_called()

    @pytest.mark.anyio
    async def test_commit_blocked_when_staged_empty(self) -> None:
        from dot.tui.app import DotApp

        entries = [FileEntry(path="only_unstaged.txt", status=" M")]

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(entries)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("c")
                await pilot.pause()
                # Commit should NOT have been called (no staged files)
                ops.commit.assert_not_called()

    @pytest.mark.anyio
    async def test_delete_file_with_confirmation(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            ops.rm.return_value = CommandResult(success=True)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("d")
                await pilot.pause()
                # Confirmation screen should be showing
                await pilot.press("y")
                await pilot.pause()
                ops.rm.assert_called_once_with("unstaged.txt")

    @pytest.mark.anyio
    async def test_delete_cancelled(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("d")
                await pilot.pause()
                await pilot.press("n")
                await pilot.pause()
                ops.rm.assert_not_called()

    @pytest.mark.anyio
    async def test_ignore_opens_modal(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            ops.add_to_gitignore.return_value = CommandResult(success=True)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("i")
                await pilot.pause()
                # GitignoreModal should be showing with pre-filled value
                await pilot.press("enter")
                await pilot.pause()
                ops.add_to_gitignore.assert_called_once_with("unstaged.txt")

    @pytest.mark.anyio
    async def test_commit_happy_path(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            ops.commit.return_value = CommandResult(success=True)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await pilot.press("c")
                await pilot.pause()
                # CommitModal should be showing
                from textual.widgets import Input

                inp = app.screen.query_one("#commit-input", Input)
                inp.value = "fix: test commit"
                await pilot.press("enter")
                await pilot.pause()
                ops.commit.assert_called_once_with("fix: test commit")


_HUNK_DIFF = "--- a/unstaged.txt\n+++ b/unstaged.txt\n@@ -1,3 +1,4 @@\n line1\n+added\n line2\n line3"

_HUNK_ENTRIES = [
    FileEntry(path="a.txt", status=" M"),
    FileEntry(path="b.txt", status=" M"),
    FileEntry(path="staged.txt", status="M "),
]


class TestMainScreenHunkStaging:
    @pytest.mark.anyio
    async def test_enter_on_diff_with_hunk_calls_apply_patch(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_HUNK_ENTRIES)
            ops.diff.return_value = _HUNK_DIFF
            ops.apply_patch.return_value = CommandResult(success=True)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                # Trigger FileSelected by moving cursor (j changes index 0->1)
                await pilot.press("j")
                await pilot.pause()

                # Focus diff directly to keep the unstaged diff visible
                # (tabbing through staged would update diff to staged file)
                app.screen.query_one("#diff").focus()
                await pilot.pause()

                assert app.screen.focused is not None
                assert app.screen.focused.id == "diff"

                await pilot.press("enter")
                await pilot.pause()

                ops.apply_patch.assert_called_once()

    @pytest.mark.anyio
    async def test_enter_on_empty_diff_does_nothing(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_TEST_ENTRIES)
            ops.apply_patch.return_value = CommandResult(success=True)
            ops.apply_patch_reverse.return_value = CommandResult(success=True)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                # Tab twice to reach diff pane (diff is empty by default)
                await pilot.press("tab")
                await pilot.pause()
                await pilot.press("tab")
                await pilot.pause()

                assert app.screen.focused is not None
                assert app.screen.focused.id == "diff"

                await pilot.press("enter")
                await pilot.pause()

                ops.apply_patch.assert_not_called()
                ops.apply_patch_reverse.assert_not_called()

    @pytest.mark.anyio
    async def test_hunk_staging_refreshes_status(self) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(_HUNK_ENTRIES)
            ops.diff.return_value = _HUNK_DIFF
            ops.apply_patch.return_value = CommandResult(success=True)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                # Trigger FileSelected
                await pilot.press("j")
                await pilot.pause()

                # Tab twice to reach diff pane
                await pilot.press("tab")
                await pilot.pause()
                await pilot.press("tab")
                await pilot.pause()

                ops.status.reset_mock()
                await pilot.press("enter")
                await pilot.pause()

                # refresh_status calls status() again
                ops.status.assert_called()

    @pytest.mark.anyio
    async def test_unstaging_calls_apply_patch_reverse(self) -> None:
        from dot.tui.app import DotApp

        staged_entries = [
            FileEntry(path="a.txt", status="M "),
            FileEntry(path="b.txt", status="M "),
        ]

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as mock_cls:
            ops = _mock_git_ops(staged_entries)
            ops.diff.return_value = _HUNK_DIFF
            ops.apply_patch_reverse.return_value = CommandResult(success=True)
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root="/tmp/test")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()

                # Move to staged pane, trigger FileSelected
                await pilot.press("tab")
                await pilot.pause()
                await pilot.press("j")
                await pilot.pause()

                # Tab to diff pane
                await pilot.press("tab")
                await pilot.pause()

                assert app.screen.focused is not None
                assert app.screen.focused.id == "diff"

                await pilot.press("enter")
                await pilot.pause()

                ops.apply_patch_reverse.assert_called_once()
