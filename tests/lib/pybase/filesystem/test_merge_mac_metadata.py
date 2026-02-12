"""Tests for merge_mac_metadata error handling."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="xattr not available on Windows",
)


class TestMergeMacMetadata:
    """Tests for merge_mac_metadata function."""

    def test_oserror_on_setxattr_is_caught(self, tmp_path: Path) -> None:
        """OSError during setxattr is silently caught (lines 48-49)."""
        data_file = tmp_path / "test.txt"
        apple_double = tmp_path / "._test.txt"
        data_file.write_text("content")
        apple_double.write_bytes(b"resource fork data")

        with patch("xattr.setxattr", side_effect=OSError("permission denied")):
            from buvis.pybase.filesystem.dir_tree.merge_mac_metadata import (
                merge_mac_metadata,
            )

            merge_mac_metadata(tmp_path)
            # Both files should still exist (merge failed silently)
            assert apple_double.exists()
            assert data_file.exists()

    def test_oserror_on_unlink_orphan_is_caught(self, tmp_path: Path) -> None:
        """OSError during orphan ._ file deletion is caught (lines 55-56)."""
        from buvis.pybase.filesystem.dir_tree.merge_mac_metadata import (
            merge_mac_metadata,
        )

        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"orphan data")
        # No corresponding data file exists

        original_unlink = Path.unlink

        def mock_unlink(self, *args, **kwargs):
            if self.name.startswith("._"):
                raise OSError("busy")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", mock_unlink):
            merge_mac_metadata(tmp_path)
            # Function completes without raising

    def test_successful_merge_removes_apple_double(self, tmp_path: Path) -> None:
        """Successful merge removes the ._ file."""
        data_file = tmp_path / "test.txt"
        apple_double = tmp_path / "._test.txt"
        data_file.write_text("content")
        apple_double.write_bytes(b"resource")

        with patch("xattr.setxattr"):
            from buvis.pybase.filesystem.dir_tree.merge_mac_metadata import (
                merge_mac_metadata,
            )

            merge_mac_metadata(tmp_path)
            assert not apple_double.exists()

    def test_orphan_apple_double_is_removed(self, tmp_path: Path) -> None:
        """Orphan ._ files (no data file) are removed."""
        from buvis.pybase.filesystem.dir_tree.merge_mac_metadata import (
            merge_mac_metadata,
        )

        apple_double = tmp_path / "._orphan.txt"
        apple_double.write_bytes(b"orphan data")
        # No corresponding data file

        merge_mac_metadata(tmp_path)
        assert not apple_double.exists()
