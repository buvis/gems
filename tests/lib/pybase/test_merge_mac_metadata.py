from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from buvis.pybase.filesystem.dir_tree.merge_mac_metadata import merge_mac_metadata


class TestMergeMacMetadata:
    def test_removes_apple_double_without_data_file(self, tmp_path: Path) -> None:
        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"\x00\x05\x16\x07")

        merge_mac_metadata(tmp_path)

        assert not apple_double.exists()

    def test_removes_apple_double_with_data_file(self, tmp_path: Path) -> None:
        data_file = tmp_path / "photo.jpg"
        data_file.write_bytes(b"\xff\xd8\xff")
        apple_double = tmp_path / "._photo.jpg"
        apple_double.write_bytes(b"\x00\x05\x16\x07resource")

        if os.name == "nt":
            merge_mac_metadata(tmp_path)
            assert not apple_double.exists()
        else:
            with patch("buvis.pybase.filesystem.dir_tree.merge_mac_metadata.xattr") as mock_xattr:
                merge_mac_metadata(tmp_path)
                mock_xattr.setxattr.assert_called_once()
                assert not apple_double.exists()

    def test_oserror_on_xattr_is_silenced(self, tmp_path: Path) -> None:
        data_file = tmp_path / "photo.jpg"
        data_file.write_bytes(b"\xff\xd8\xff")
        apple_double = tmp_path / "._photo.jpg"
        apple_double.write_bytes(b"\x00\x05\x16\x07")

        if os.name != "nt":
            with patch("buvis.pybase.filesystem.dir_tree.merge_mac_metadata.xattr") as mock_xattr:
                mock_xattr.setxattr.side_effect = OSError("xattr failed")
                merge_mac_metadata(tmp_path)
                assert apple_double.exists()

    def test_oserror_on_unlink_orphan_is_silenced(self, tmp_path: Path) -> None:
        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"\x00")

        with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
            merge_mac_metadata(tmp_path)

    def test_skips_non_file_apple_double(self, tmp_path: Path) -> None:
        apple_dir = tmp_path / "._subdir"
        apple_dir.mkdir()

        merge_mac_metadata(tmp_path)

        assert apple_dir.exists()

    def test_nested_apple_double(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        apple_double = sub / "._nested.txt"
        apple_double.write_bytes(b"\x00")

        merge_mac_metadata(tmp_path)

        assert not apple_double.exists()
