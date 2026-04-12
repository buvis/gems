from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from buvis.pybase.result import CommandResult
from dot.tui.commands.browse import DirEntry, TrackingStatus
from dot.tui.commands.secrets import SecretEntry
from dot.tui.models import BranchInfo, FileEntry

TERMINAL_SIZES = [
    pytest.param((80, 24), id="80x24"),
    pytest.param((120, 40), id="120x40"),
    pytest.param((40, 15), id="40x15"),
]


def _long_diff() -> str:
    """Build a realistic 60+ line unified diff."""
    lines = [
        "diff --git a/config/shell/aliases.sh b/config/shell/aliases.sh",
        "index 1a2b3c4..5d6e7f8 100644",
        "--- a/config/shell/aliases.sh",
        "+++ b/config/shell/aliases.sh",
        "@@ -1,20 +1,25 @@",
    ]
    for i in range(1, 21):
        if i % 5 == 0:
            lines.append(f"-old_alias_{i}='echo removed'")
            lines.append(f"+new_alias_{i}='echo replaced'")
        elif i % 7 == 0:
            lines.append(f"+added_alias_{i}='echo new'")
        else:
            lines.append(f" existing_alias_{i}='echo keep'")
    lines.append("@@ -30,15 +35,20 @@")
    for i in range(30, 55):
        if i % 3 == 0:
            lines.append(f"-removed_line_{i}='old value'")
            lines.append(f"+replaced_line_{i}='new value'")
        else:
            lines.append(f" context_line_{i}='unchanged'")
    return "\n".join(lines)


def _many_file_entries(prefix: str, count: int, status: str) -> list[FileEntry]:
    return [FileEntry(path=f"{prefix}/file_{i:02d}.txt", status=status) for i in range(count)]


def _mock_git_ops_with_content() -> MagicMock:
    """GitOps mock with overflowing content for snapshot tests."""
    ops = MagicMock()
    staged = _many_file_entries("staged", 15, "M ")
    unstaged = _many_file_entries("unstaged", 18, " M")
    ops.status.return_value = staged + unstaged
    ops.branch_info.return_value = BranchInfo(
        name="feature/snapshot-tests",
        ahead=3,
        behind=1,
        secret_count=2,
    )
    ops.diff.return_value = _long_diff()
    ops.stage.return_value = CommandResult(success=True)
    ops.unstage.return_value = CommandResult(success=True)
    ops.has_uncommitted_changes.return_value = True
    ops.has_unpushed_commits.return_value = True
    ops.shell.is_command_available.return_value = False
    return ops


def _many_dir_entries(count: int) -> list[DirEntry]:
    """Build 30+ DirEntry items with mixed types and tracking states."""
    entries: list[DirEntry] = [DirEntry(name="..", path="/dotfiles", is_dir=True, status=TrackingStatus.TRACKED)]
    statuses = [TrackingStatus.TRACKED, TrackingStatus.UNTRACKED, TrackingStatus.IGNORED]
    for i in range(count):
        is_dir = i % 5 == 0
        name = f".config_{i:02d}" if is_dir else f".file_{i:02d}.conf"
        entries.append(
            DirEntry(
                name=name,
                path=f"/dotfiles/{name}",
                is_dir=is_dir,
                status=statuses[i % 3],
            )
        )
    return entries


class TestMainScreenSnapshots:
    @pytest.mark.snapshot
    @pytest.mark.dot
    @pytest.mark.parametrize("terminal_size", TERMINAL_SIZES)
    def test_main_screen_with_overflowing_content(self, snap_compare, terminal_size):
        from dot.tui.app import DotApp

        mock_ops = _mock_git_ops_with_content()

        with patch("dot.tui.app.ShellAdapter"), patch("dot.tui.app.GitOps") as cls:
            cls.return_value = mock_ops
            app = DotApp(dotfiles_root="/tmp/test")
            assert snap_compare(app, terminal_size=terminal_size)


class TestBrowseScreenSnapshots:
    @pytest.mark.snapshot
    @pytest.mark.dot
    @pytest.mark.parametrize("terminal_size", TERMINAL_SIZES)
    def test_browse_screen_with_many_entries(self, snap_compare, terminal_size):
        from dot.tui.app import DotApp

        mock_ops = _mock_git_ops_with_content()
        entries = _many_dir_entries(35)

        with (
            patch("dot.tui.app.ShellAdapter"),
            patch("dot.tui.app.GitOps") as cls,
            patch("dot.tui.screens.browse.list_directory", return_value=entries),
        ):
            cls.return_value = mock_ops
            app = DotApp(dotfiles_root="/tmp/test")

            async def push_browse(pilot):
                await pilot.pause()
                await pilot.press("b")
                await pilot.pause()

            assert snap_compare(app, terminal_size=terminal_size, run_before=push_browse)


def _many_secret_entries(count: int) -> list[SecretEntry]:
    """Build 20+ SecretEntry items with mixed revealed/hidden states."""
    return [
        SecretEntry(
            path=f".secrets/key_{i:02d}.gpg",
            status="revealed" if i % 3 == 0 else "hidden",
        )
        for i in range(count)
    ]


class TestSecretsScreenSnapshots:
    @pytest.mark.snapshot
    @pytest.mark.dot
    @pytest.mark.parametrize("terminal_size", TERMINAL_SIZES)
    def test_secrets_screen_with_many_secrets(self, snap_compare, terminal_size):
        from dot.tui.app import DotApp

        mock_ops = _mock_git_ops_with_content()
        mock_ops.shell.is_command_available.return_value = True
        secrets = _many_secret_entries(25)

        with (
            patch("dot.tui.app.ShellAdapter"),
            patch("dot.tui.app.GitOps") as cls,
            patch("dot.tui.screens.secrets.list_secrets", return_value=secrets),
        ):
            cls.return_value = mock_ops
            app = DotApp(dotfiles_root="/tmp/test")

            async def push_secrets(pilot):
                await pilot.pause()
                await pilot.press("S")
                await pilot.pause()

            assert snap_compare(app, terminal_size=terminal_size, run_before=push_secrets)
