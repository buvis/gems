from __future__ import annotations

import platform
from pathlib import Path

import pytest

from buvis.pybase.filesystem import DirTree


class TestCountFiles:
    def test_counts_files_in_flat_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        assert DirTree.count_files(tmp_path) == 2

    def test_counts_files_recursively(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").touch()
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").touch()
        assert DirTree.count_files(tmp_path) == 2

    def test_returns_zero_for_empty_directory(self, tmp_path: Path) -> None:
        assert DirTree.count_files(tmp_path) == 0

    def test_excludes_directories_from_count(self, tmp_path: Path) -> None:
        (tmp_path / "dir").mkdir()
        (tmp_path / "file.txt").touch()
        assert DirTree.count_files(tmp_path) == 1


class TestGetMaxDepth:
    def test_returns_zero_for_empty_directory(self, tmp_path: Path) -> None:
        assert DirTree.get_max_depth(tmp_path) == 0

    def test_returns_one_for_flat_directory(self, tmp_path: Path) -> None:
        (tmp_path / "file.txt").touch()
        assert DirTree.get_max_depth(tmp_path) == 1

    def test_returns_correct_depth_for_nested(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").touch()
        assert DirTree.get_max_depth(tmp_path) == 4  # a/b/c/file.txt


class TestDeleteByExtension:
    def test_deletes_matching_extensions(self, tmp_path: Path) -> None:
        txt = tmp_path / "delete.txt"
        txt.touch()
        DirTree.delete_by_extension(tmp_path, [".txt"])
        assert not txt.exists()

    def test_keeps_non_matching_files(self, tmp_path: Path) -> None:
        keep = tmp_path / "keep.log"
        keep.touch()
        DirTree.delete_by_extension(tmp_path, [".txt"])
        assert keep.exists()

    def test_handles_case_insensitive_extensions(self, tmp_path: Path) -> None:
        upper = tmp_path / "file.TXT"
        upper.touch()
        DirTree.delete_by_extension(tmp_path, [".txt"])
        assert not upper.exists()

    def test_preserves_stfolder_contents(self, tmp_path: Path) -> None:
        stfolder = tmp_path / ".stfolder"
        stfolder.mkdir()
        protected = stfolder / "marker.txt"
        protected.touch()
        DirTree.delete_by_extension(tmp_path, [".txt"])
        assert protected.exists()


class TestNormalizeFileExtensions:
    def test_lowercases_extensions(self, tmp_path: Path) -> None:
        upper = tmp_path / "file.TXT"
        upper.touch()
        DirTree.normalize_file_extensions(tmp_path)
        # On case-insensitive filesystems, both paths point to same file
        assert (tmp_path / "file.txt").exists()

    def test_renames_jpeg_to_jpg(self, tmp_path: Path) -> None:
        jpeg = tmp_path / "photo.jpeg"
        jpeg.touch()
        DirTree.normalize_file_extensions(tmp_path)
        assert (tmp_path / "photo.jpg").exists()
        assert not jpeg.exists()

    def test_renames_mp2_to_mp3(self, tmp_path: Path) -> None:
        mp2 = tmp_path / "song.mp2"
        mp2.touch()
        DirTree.normalize_file_extensions(tmp_path)
        assert (tmp_path / "song.mp3").exists()
        assert not mp2.exists()

    def test_renames_fla_to_flac(self, tmp_path: Path) -> None:
        fla = tmp_path / "audio.fla"
        fla.touch()
        DirTree.normalize_file_extensions(tmp_path)
        assert (tmp_path / "audio.flac").exists()
        assert not fla.exists()


class TestRemoveEmptyDirectories:
    def test_removes_empty_leaf_directory(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        DirTree.remove_empty_directories(tmp_path)
        assert not empty.exists()

    def test_removes_nested_empty_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        DirTree.remove_empty_directories(tmp_path)
        assert not (tmp_path / "a").exists()

    def test_preserves_directories_with_files(self, tmp_path: Path) -> None:
        nonempty = tmp_path / "keep"
        nonempty.mkdir()
        (nonempty / "file.txt").touch()
        DirTree.remove_empty_directories(tmp_path)
        assert nonempty.exists()
        assert (nonempty / "file.txt").exists()


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="merge_mac_metadata requires macOS xattr support",
)
class TestMergeMacMetadata:
    def test_removes_orphan_underscore_files(self, tmp_path: Path) -> None:
        orphan = tmp_path / "._orphan.txt"
        orphan.write_bytes(b"data")
        DirTree.merge_mac_metadata(tmp_path)
        assert not orphan.exists()

    def test_merges_xattr_from_underscore_files(self, tmp_path: Path) -> None:
        import xattr

        data_file = tmp_path / "file.txt"
        data_file.write_text("content")
        apple_double = tmp_path / "._file.txt"
        apple_double.write_bytes(b"resource fork data")

        DirTree.merge_mac_metadata(tmp_path)

        assert not apple_double.exists()
        attrs = xattr.listxattr(str(data_file))
        assert "com.apple.ResourceFork" in attrs
