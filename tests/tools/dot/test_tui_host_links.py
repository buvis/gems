from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.result import CommandResult
from dot.tui.models import BranchInfo, FileEntry
from dot.tui.widgets.diff_view import DiffView
from dot.tui.widgets.status_bar import StatusBar
from textual.app import App


def _mock_git_ops(
    entries: list[FileEntry] | None = None,
    hide_error: str | None = None,
) -> MagicMock:
    ops = MagicMock()
    ops.status.return_value = (entries or [], hide_error)
    ops.branch_info.return_value = BranchInfo(name="master")
    ops.diff.return_value = ""
    ops.stage.return_value = CommandResult(success=True)
    ops.unstage.return_value = CommandResult(success=True)
    ops.has_uncommitted_changes.return_value = False
    ops.has_unpushed_commits.return_value = False
    ops.shell.is_command_available.return_value = False
    return ops


def _write_manifest(root: Path, line: str) -> None:
    manifest = root / ".config" / "buvis" / "host-links"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(line + "\n")


def _status_text(app: App[None]) -> str:
    return str(app.screen.query_one("#status-bar", StatusBar).render())


class TestTuiHostLinks:
    @pytest.mark.anyio
    async def test_status_bar_shows_link_problem_for_missing_host_file(self, tmp_path: Path) -> None:
        from dot.tui.app import DotApp

        _write_manifest(tmp_path, "linked.conf => hosts/linked.conf")
        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.DotGitService") as mock_cls:
            mock_cls.return_value = _mock_git_ops()

            app = DotApp(dotfiles_root=str(tmp_path))
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                assert "1 link problem(s)" in _status_text(app)

    @pytest.mark.anyio
    async def test_status_bar_hides_link_problems_without_manifest(self, tmp_path: Path) -> None:
        from dot.tui.app import DotApp

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.DotGitService") as mock_cls:
            mock_cls.return_value = _mock_git_ops()

            app = DotApp(dotfiles_root=str(tmp_path))
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                assert "link problem" not in _status_text(app)

    @pytest.mark.anyio
    async def test_l_key_links_host_file_and_reports_it(self, tmp_path: Path) -> None:
        from dot.tui.app import DotApp

        source = tmp_path / "hosts" / "linked.conf"
        source.parent.mkdir()
        source.write_text("host data")
        _write_manifest(tmp_path, "linked.conf => hosts/linked.conf")
        ops = _mock_git_ops()
        ops.hooks_path.return_value = None
        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.DotGitService") as mock_cls:
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root=str(tmp_path))
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                diff_view = app.screen.query_one("#diff", DiffView)
                diff_view.update_diff = MagicMock()
                await pilot.press("L")
                await pilot.pause()

                assert "linked linked.conf" in diff_view.update_diff.call_args.args[0]
                assert (tmp_path / "linked.conf").is_symlink()
                assert (tmp_path / "linked.conf").read_text() == "host data"
                assert "link problem" not in _status_text(app)

    @pytest.mark.anyio
    async def test_l_key_reports_current_when_nothing_to_link(self, tmp_path: Path) -> None:
        from dot.tui.app import DotApp

        ops = _mock_git_ops()
        ops.hooks_path.return_value = None
        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.DotGitService") as mock_cls:
            mock_cls.return_value = ops

            app = DotApp(dotfiles_root=str(tmp_path))
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                diff_view = app.screen.query_one("#diff", DiffView)
                diff_view.update_diff = MagicMock()
                await pilot.press("L")
                await pilot.pause()

                diff_view.update_diff.assert_called_once_with("Host links current")
