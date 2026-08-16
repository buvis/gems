from __future__ import annotations

import dataclasses

import pytest
from dot.git.models import BranchInfo, FileEntry


class TestFileEntry:
    def test_construction(self) -> None:
        entry = FileEntry(path=".bashrc", status="M ", is_secret=True)

        assert entry.path == ".bashrc"
        assert entry.status == "M "
        assert entry.is_secret is True

    def test_defaults(self) -> None:
        entry = FileEntry(path=".vimrc", status="??")

        assert entry.is_secret is False

    def test_frozen(self) -> None:
        entry = FileEntry(path=".bashrc", status="M ")

        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(entry, "path", "other")


class TestBranchInfo:
    def test_construction(self) -> None:
        info = BranchInfo(name="main", ahead=3, behind=1, secret_count=5)

        assert info.name == "main"
        assert info.ahead == 3
        assert info.behind == 1
        assert info.secret_count == 5

    def test_defaults(self) -> None:
        info = BranchInfo(name="master")

        assert info.ahead == 0
        assert info.behind == 0
        assert info.secret_count == 0

    def test_frozen(self) -> None:
        info = BranchInfo(name="master")

        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(info, "name", "other")


class TestTuiModelsShim:
    def test_branch_info_reexport_is_same_class_as_git_models(self) -> None:
        from dot.tui.models import BranchInfo as ShimBranchInfo

        assert ShimBranchInfo is BranchInfo

    def test_file_entry_reexport_is_same_class_as_git_models(self) -> None:
        from dot.tui.models import FileEntry as ShimFileEntry

        assert ShimFileEntry is FileEntry
