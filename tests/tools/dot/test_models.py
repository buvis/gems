from __future__ import annotations

import dataclasses

import pytest
from dot.tui.models import BranchInfo, FileEntry


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
            entry.path = "other"  # type: ignore[misc]


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
            info.name = "other"  # type: ignore[misc]
