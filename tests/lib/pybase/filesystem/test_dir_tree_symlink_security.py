"""Tests for symlink security in DirTree."""

from __future__ import annotations

from pathlib import Path

from buvis.pybase.filesystem import DirTree


class TestIsSafePath:
    def test_regular_file_is_safe(self, tmp_path: Path) -> None:
        file = tmp_path / "file.txt"
        file.touch()

        assert DirTree._is_safe_path(file, [tmp_path]) is True

    def test_symlink_within_allowed_dir_is_safe(self, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        target.touch()
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        assert DirTree._is_safe_path(link, [tmp_path]) is True

    def test_symlink_outside_allowed_dir_is_unsafe(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        outside = tmp_path / "outside" / "target.txt"
        outside.parent.mkdir()
        outside.touch()
        link = allowed / "escape.txt"
        link.symlink_to(outside)

        assert DirTree._is_safe_path(link, [allowed]) is False

    def test_broken_symlink_is_unsafe(self, tmp_path: Path) -> None:
        link = tmp_path / "broken.txt"
        link.symlink_to(tmp_path / "nonexistent")

        assert DirTree._is_safe_path(link, [tmp_path]) is False

    def test_multiple_allowed_bases(self, tmp_path: Path) -> None:
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        file = dir2 / "file.txt"
        file.touch()

        assert DirTree._is_safe_path(file, [dir1, dir2]) is True


class TestSafeRglob:
    def test_yields_safe_paths(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()

        paths = list(DirTree._safe_rglob(tmp_path))

        assert len(paths) == 1
        assert paths[0] == tmp_path / "file.txt"

    def test_skips_unsafe_symlinks(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        (allowed / "safe.txt").touch()

        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").touch()
        (allowed / "escape").symlink_to(outside)

        paths = list(DirTree._safe_rglob(allowed))

        # Only safe.txt - escape symlink points outside so is filtered
        assert len(paths) == 1
        assert paths[0].name == "safe.txt"


class TestDirTreeSymlinkIntegration:
    def test_count_files_ignores_symlink_escape(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        (allowed / "real.txt").touch()

        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").touch()
        (allowed / "escape").symlink_to(outside)

        assert DirTree.count_files(allowed) == 1  # only real.txt

    def test_delete_by_extension_skips_symlink_escape(self, tmp_path: Path) -> None:
        allowed = tmp_path / "allowed"
        allowed.mkdir()

        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "keep.txt"
        target.touch()
        (allowed / "escape").symlink_to(outside)

        DirTree.delete_by_extension(allowed, [".txt"])

        assert target.exists()  # outside file not deleted
