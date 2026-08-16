from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dot.git.service import DotGitService
from dot.tui.commands.browse import (
    TrackingStatus,
    _query_git_sets,
    get_tracking_status,
    list_directory,
)


@pytest.fixture
def shell() -> MagicMock:
    mock = MagicMock()
    mock.exe.return_value = ("", "")
    return mock


@pytest.fixture
def git_ops(shell: MagicMock, tmp_path: Path) -> DotGitService:
    service = DotGitService(shell=shell, dotfiles_root=str(tmp_path))
    service.ls_files = MagicMock(return_value=set())
    service.check_ignore = MagicMock(return_value=set())
    return service


class TestQueryGitSets:
    def test_calls_ls_files_with_rel_query_for_tracked_set(self, git_ops: DotGitService) -> None:
        git_ops.ls_files.return_value = {"a.txt", "b.txt"}

        _query_git_sets(git_ops, "subdir")

        git_ops.ls_files.assert_called_once_with("subdir")

    def test_calls_check_ignore_with_wildcard_pathspec_for_ignored_set(self, git_ops: DotGitService) -> None:
        git_ops.check_ignore.return_value = {"c.txt"}

        _query_git_sets(git_ops, "subdir")

        git_ops.check_ignore.assert_called_once_with("subdir/*")

    def test_wildcard_pathspec_appends_to_dot_relative_query(self, git_ops: DotGitService) -> None:
        _query_git_sets(git_ops, ".")

        git_ops.check_ignore.assert_called_once_with("./*")

    def test_returns_tracked_and_ignored_sets_from_service(self, git_ops: DotGitService) -> None:
        git_ops.ls_files.return_value = {"a.txt"}
        git_ops.check_ignore.return_value = {"b.txt"}

        tracked, ignored = _query_git_sets(git_ops, "subdir")

        assert tracked == {"a.txt"}
        assert ignored == {"b.txt"}

    def test_returns_empty_sets_when_service_returns_empty(self, git_ops: DotGitService) -> None:
        tracked, ignored = _query_git_sets(git_ops, ".")

        assert tracked == set()
        assert ignored == set()

    def test_returns_service_sets_without_transformation(self, git_ops: DotGitService) -> None:
        tracked_set = {"a.txt"}
        ignored_set = {"b.txt"}
        git_ops.ls_files.return_value = tracked_set
        git_ops.check_ignore.return_value = ignored_set

        tracked, ignored = _query_git_sets(git_ops, "subdir")

        assert tracked is tracked_set
        assert ignored is ignored_set


class TestListDirectoryBasic:
    def test_empty_directory_returns_only_parent_entry(self, git_ops: DotGitService, tmp_path: Path) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = list_directory(git_ops, str(subdir))

        assert len(result) == 1
        assert result[0].name == ".."
        assert result[0].is_dir is True

    def test_lists_files_with_correct_is_dir_flag(self, git_ops: DotGitService, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()
        (tmp_path / "subdir").mkdir()

        result = list_directory(git_ops, str(tmp_path))

        names = {e.name: e.is_dir for e in result if e.name != ".."}
        assert names["file.txt"] is False
        assert names["subdir"] is True

    def test_parent_entry_present_for_non_root(self, git_ops: DotGitService, tmp_path: Path) -> None:
        result = list_directory(git_ops, str(tmp_path))

        parent = [e for e in result if e.name == ".."]
        assert len(parent) == 1

    def test_no_parent_entry_at_filesystem_root(self, git_ops: DotGitService) -> None:
        result = list_directory(git_ops, "/")

        parent = [e for e in result if e.name == ".."]
        assert len(parent) == 0


class TestListDirectoryDotfileFilter:
    def test_at_dotfiles_root_only_dotfiles_returned(self, git_ops: DotGitService, tmp_path: Path) -> None:
        (tmp_path / ".bashrc").touch()
        (tmp_path / ".config").mkdir()
        (tmp_path / "README.md").touch()
        (tmp_path / "bin").mkdir()

        result = list_directory(git_ops, str(tmp_path))

        names = {e.name for e in result if e.name != ".."}
        assert ".bashrc" in names
        assert ".config" in names
        assert "README.md" not in names
        assert "bin" not in names

    def test_at_subdirectory_all_entries_returned(self, git_ops: DotGitService, tmp_path: Path) -> None:
        subdir = tmp_path / ".config"
        subdir.mkdir()
        (subdir / "settings.json").touch()
        (subdir / ".hidden").touch()

        result = list_directory(git_ops, str(subdir))

        names = {e.name for e in result if e.name != ".."}
        assert "settings.json" in names
        assert ".hidden" in names


class TestListDirectoryTrackingStatus:
    def test_tracked_file_gets_tracked_status(self, git_ops: DotGitService, tmp_path: Path) -> None:
        (tmp_path / ".bashrc").touch()
        git_ops.ls_files.return_value = {".bashrc"}

        result = list_directory(git_ops, str(tmp_path))

        entry = next(e for e in result if e.name == ".bashrc")
        assert entry.status == TrackingStatus.TRACKED

    def test_ignored_file_gets_ignored_status(self, git_ops: DotGitService, tmp_path: Path) -> None:
        (tmp_path / ".cache").touch()
        git_ops.check_ignore.return_value = {".cache"}

        result = list_directory(git_ops, str(tmp_path))

        entry = next(e for e in result if e.name == ".cache")
        assert entry.status == TrackingStatus.IGNORED

    def test_untracked_file_gets_untracked_status(self, git_ops: DotGitService, tmp_path: Path) -> None:
        (tmp_path / ".newfile").touch()

        result = list_directory(git_ops, str(tmp_path))

        entry = next(e for e in result if e.name == ".newfile")
        assert entry.status == TrackingStatus.UNTRACKED

    def test_mixed_statuses_in_directory(self, git_ops: DotGitService, tmp_path: Path) -> None:
        (tmp_path / ".bashrc").touch()
        (tmp_path / ".cache").touch()
        (tmp_path / ".newfile").touch()
        git_ops.ls_files.return_value = {".bashrc"}
        git_ops.check_ignore.return_value = {".cache"}

        result = list_directory(git_ops, str(tmp_path))

        entries = {e.name: e.status for e in result if e.name != ".."}
        assert entries[".bashrc"] == TrackingStatus.TRACKED
        assert entries[".cache"] == TrackingStatus.IGNORED
        assert entries[".newfile"] == TrackingStatus.UNTRACKED


class TestGetTrackingStatus:
    def test_returns_tracked_when_path_in_ls_files_result(self, git_ops: DotGitService) -> None:
        git_ops.ls_files.return_value = {".bashrc"}

        result = get_tracking_status(git_ops, ".bashrc")

        assert result == TrackingStatus.TRACKED

    def test_calls_ls_files_with_exact_path(self, git_ops: DotGitService) -> None:
        get_tracking_status(git_ops, ".bashrc")

        git_ops.ls_files.assert_called_once_with(".bashrc")

    def test_returns_ignored_when_path_in_check_ignore_result(self, git_ops: DotGitService) -> None:
        git_ops.check_ignore.return_value = {".cache"}

        result = get_tracking_status(git_ops, ".cache")

        assert result == TrackingStatus.IGNORED

    def test_calls_check_ignore_with_exact_path_when_not_tracked(self, git_ops: DotGitService) -> None:
        get_tracking_status(git_ops, ".cache")

        git_ops.check_ignore.assert_called_once_with(".cache")

    def test_returns_untracked_when_path_in_neither_set(self, git_ops: DotGitService) -> None:
        result = get_tracking_status(git_ops, ".newfile")

        assert result == TrackingStatus.UNTRACKED

    def test_tracked_takes_precedence_over_ignored(self, git_ops: DotGitService) -> None:
        git_ops.ls_files.return_value = {".bashrc"}
        git_ops.check_ignore.return_value = {".bashrc"}

        result = get_tracking_status(git_ops, ".bashrc")

        assert result == TrackingStatus.TRACKED
