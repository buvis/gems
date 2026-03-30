from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dot.tui.commands.browse import DirEntry, TrackingStatus, get_tracking_status, list_directory
from dot.tui.git_ops import GitOps


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_ops(shell: MagicMock, tmp_path: Path) -> GitOps:
    return GitOps(shell=shell, dotfiles_root=str(tmp_path))


class TestListDirectoryBasic:
    def test_empty_directory_returns_only_parent_entry(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        shell.exe.return_value = ("", "")

        result = list_directory(git_ops, str(subdir))

        assert len(result) == 1
        assert result[0].name == ".."
        assert result[0].is_dir is True

    def test_lists_files_with_correct_is_dir_flag(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / "file.txt").touch()
        (tmp_path / "subdir").mkdir()
        shell.exe.return_value = ("", "")

        result = list_directory(git_ops, str(tmp_path))

        names = {e.name: e.is_dir for e in result if e.name != ".."}
        assert names["file.txt"] is False
        assert names["subdir"] is True

    def test_parent_entry_present_for_non_root(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        shell.exe.return_value = ("", "")

        result = list_directory(git_ops, str(tmp_path))

        parent = [e for e in result if e.name == ".."]
        assert len(parent) == 1

    def test_no_parent_entry_at_filesystem_root(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.exe.return_value = ("", "")

        result = list_directory(git_ops, "/")

        parent = [e for e in result if e.name == ".."]
        assert len(parent) == 0


class TestListDirectoryDotfileFilter:
    def test_at_dotfiles_root_only_dotfiles_returned(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".bashrc").touch()
        (tmp_path / ".config").mkdir()
        (tmp_path / "README.md").touch()
        (tmp_path / "bin").mkdir()
        shell.exe.return_value = ("", "")

        result = list_directory(git_ops, str(tmp_path))

        names = {e.name for e in result if e.name != ".."}
        assert ".bashrc" in names
        assert ".config" in names
        assert "README.md" not in names
        assert "bin" not in names

    def test_at_subdirectory_all_entries_returned(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        subdir = tmp_path / ".config"
        subdir.mkdir()
        (subdir / "settings.json").touch()
        (subdir / ".hidden").touch()
        shell.exe.return_value = ("", "")

        result = list_directory(git_ops, str(subdir))

        names = {e.name for e in result if e.name != ".."}
        assert "settings.json" in names
        assert ".hidden" in names


class TestListDirectoryTrackingStatus:
    def test_tracked_file_gets_tracked_status(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".bashrc").touch()
        shell.exe.side_effect = [
            ("", ".bashrc\n"),  # cfg ls-files
            ("", ""),  # cfg check-ignore
        ]

        result = list_directory(git_ops, str(tmp_path))

        entry = next(e for e in result if e.name == ".bashrc")
        assert entry.status == TrackingStatus.TRACKED

    def test_ignored_file_gets_ignored_status(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".cache").touch()
        shell.exe.side_effect = [
            ("", ""),  # cfg ls-files (not tracked)
            ("", ".cache\n"),  # cfg check-ignore
        ]

        result = list_directory(git_ops, str(tmp_path))

        entry = next(e for e in result if e.name == ".cache")
        assert entry.status == TrackingStatus.IGNORED

    def test_untracked_file_gets_untracked_status(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".newfile").touch()
        shell.exe.side_effect = [
            ("", ""),  # cfg ls-files (not tracked)
            ("", ""),  # cfg check-ignore (not ignored)
        ]

        result = list_directory(git_ops, str(tmp_path))

        entry = next(e for e in result if e.name == ".newfile")
        assert entry.status == TrackingStatus.UNTRACKED

    def test_mixed_statuses_in_directory(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".bashrc").touch()
        (tmp_path / ".cache").touch()
        (tmp_path / ".newfile").touch()
        shell.exe.side_effect = [
            ("", ".bashrc\n"),  # cfg ls-files
            ("", ".cache\n"),  # cfg check-ignore
        ]

        result = list_directory(git_ops, str(tmp_path))

        entries = {e.name: e.status for e in result if e.name != ".."}
        assert entries[".bashrc"] == TrackingStatus.TRACKED
        assert entries[".cache"] == TrackingStatus.IGNORED
        assert entries[".newfile"] == TrackingStatus.UNTRACKED


class TestListDirectoryErrorHandling:
    def test_ls_files_error_treats_all_as_untracked(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".bashrc").touch()
        shell.exe.side_effect = [
            ("fatal: not a git repository", ""),  # cfg ls-files error
            ("", ""),  # cfg check-ignore
        ]

        result = list_directory(git_ops, str(tmp_path))

        entry = next(e for e in result if e.name == ".bashrc")
        assert entry.status == TrackingStatus.UNTRACKED

    def test_check_ignore_error_treats_non_tracked_as_untracked(
        self, git_ops: GitOps, shell: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / ".bashrc").touch()
        (tmp_path / ".cache").touch()
        shell.exe.side_effect = [
            ("", ".bashrc\n"),  # cfg ls-files (bashrc tracked)
            ("check-ignore failed", ""),  # cfg check-ignore error
        ]

        result = list_directory(git_ops, str(tmp_path))

        bashrc = next(e for e in result if e.name == ".bashrc")
        cache = next(e for e in result if e.name == ".cache")
        assert bashrc.status == TrackingStatus.TRACKED
        assert cache.status == TrackingStatus.UNTRACKED


class TestGetTrackingStatus:
    def test_returns_tracked_when_ls_files_matches(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("", ".bashrc\n"),  # cfg ls-files returns the path
        ]

        result = get_tracking_status(git_ops, ".bashrc")

        assert result == TrackingStatus.TRACKED

    def test_returns_ignored_when_check_ignore_matches(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("", ""),  # cfg ls-files (not tracked)
            ("", ".cache\n"),  # cfg check-ignore returns the path
        ]

        result = get_tracking_status(git_ops, ".cache")

        assert result == TrackingStatus.IGNORED

    def test_returns_untracked_when_neither_matches(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("", ""),  # cfg ls-files (not tracked)
            ("", ""),  # cfg check-ignore (not ignored)
        ]

        result = get_tracking_status(git_ops, ".newfile")

        assert result == TrackingStatus.UNTRACKED

    def test_tracked_wins_over_ignored(
        self, git_ops: GitOps, shell: MagicMock
    ) -> None:
        shell.exe.side_effect = [
            ("", ".bashrc\n"),  # cfg ls-files returns the path
        ]

        result = get_tracking_status(git_ops, ".bashrc")

        assert result == TrackingStatus.TRACKED
