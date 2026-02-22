from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from buvis.pybase.filesystem.dir_tree.merge_mac_metadata import merge_mac_metadata

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="xattr not available on Windows",
)


class TestMergeMacMetadata:
    """Tests for merge_mac_metadata function."""

    def test_orphan_apple_double_is_removed(self, tmp_path: Path) -> None:
        """Orphan ._ files (no data file) are removed."""
        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"\x00\x05\x16\x07")

        merge_mac_metadata(tmp_path)

        assert not apple_double.exists()

    def test_successful_merge_removes_apple_double(self, tmp_path: Path) -> None:
        """Successful merge removes the ._ file."""
        data_file = tmp_path / "photo.jpg"
        data_file.write_bytes(b"\xff\xd8\xff")
        apple_double = tmp_path / "._photo.jpg"
        apple_double.write_bytes(b"\x00\x05\x16\x07resource")

        with patch("buvis.pybase.filesystem.dir_tree.merge_mac_metadata.xattr") as mock_xattr:
            merge_mac_metadata(tmp_path)
            mock_xattr.setxattr.assert_called_once()
            assert not apple_double.exists()

    def test_oserror_on_setxattr_is_caught(self, tmp_path: Path) -> None:
        """OSError during setxattr is silently caught."""
        data_file = tmp_path / "photo.jpg"
        data_file.write_bytes(b"\xff\xd8\xff")
        apple_double = tmp_path / "._photo.jpg"
        apple_double.write_bytes(b"\x00\x05\x16\x07")

        with patch("buvis.pybase.filesystem.dir_tree.merge_mac_metadata.xattr") as mock_xattr:
            mock_xattr.setxattr.side_effect = OSError("xattr failed")
            merge_mac_metadata(tmp_path)
            assert apple_double.exists()
            assert data_file.exists()

    def test_oserror_on_unlink_orphan_is_caught(self, tmp_path: Path) -> None:
        """OSError during orphan ._ file deletion is caught."""
        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"\x00")

        original_unlink = Path.unlink

        def mock_unlink(self, *args, **kwargs):
            if self.name.startswith("._"):
                raise OSError("busy")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", mock_unlink):
            merge_mac_metadata(tmp_path)

    def test_skips_non_file_apple_double(self, tmp_path: Path) -> None:
        """Directories named ._ are not processed."""
        apple_dir = tmp_path / "._subdir"
        apple_dir.mkdir()

        merge_mac_metadata(tmp_path)

        assert apple_dir.exists()

    def test_nested_apple_double(self, tmp_path: Path) -> None:
        """Recursively finds ._ files in subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        apple_double = sub / "._nested.txt"
        apple_double.write_bytes(b"\x00")

        merge_mac_metadata(tmp_path)

        assert not apple_double.exists()
